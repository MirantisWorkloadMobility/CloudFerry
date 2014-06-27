import osCommon
import subprocess
import logging
from utils import forward_agent, up_ssh_tunnel
from fabric.api import run, settings, env
LOG = logging.getLogger(__name__)


class Importer(osCommon.osCommon):
    def __init__(self, config):
        super(Importer, self).__init__(config)

    def upload(self, data, config_from):
        LOG.info("Start migrate instance")
        LOG.debug("| creating new instance")
        new_instance = self.create_instance(data)
        LOG.debug("| wait for instance activating")
        self.wait_for_status(self.nova_client.servers, new_instance.id, 'ACTIVE')
        LOG.debug("| sync delta")
        self.import_instance_delta(data, new_instance, config_from)
        LOG.debug("| migrateVolumes")
        self.import_volumes(data, new_instance)

    def create_instance(self, data):
        return self.nova_client.servers.create(name=data['name'],
                                               image=self.get_image(self.ensure_param(data, 'image')),
                                               flavor=self.get_flavor(self.ensure_param(data, 'flavor')),
                                               meta=self.ensure_param(data, 'metadata'),
                                               security_groups=self.ensure_param(data, 'security_groups'),
                                               key_name=self.get_key_name(self.ensure_param(data, 'key')),
                                               nics=self.prepare_networks(data['networks']),
                                               #availability_zone=self.ensure_param(data, 'availability_zone'),
                                               config_drive=self.ensure_param(data, 'config_drive'),
                                               disk_config=self.ensure_param(data, 'diskConfig')
                                               )

    def ensure_param(self, data, name, rules_name=None):
        if rules_name is None:
            rules_name = name
        import_rules = self.config['import_rules']
        if rules_name in import_rules['overwrite']:
            return import_rules['overwrite'][rules_name]
        if name in data:
            return data[name]
        if rules_name in import_rules['default']:
            return import_rules['default'][rules_name]
        return None

    def get_image(self, image_info):
        if 'id' in image_info:
            return self.nova_client.images.get(image_info['id'])
        if 'name' in image_info:
            return self.nova_client.images.find(name=image_info['name'])

    def get_flavor(self, flavor_info):
        if 'id' in flavor_info:
            return self.nova_client.flavors.get(flavor_info['id'])
        if 'name' in flavor_info:
            return self.nova_client.flavors.find(name=flavor_info['name'])

    def get_key_name(self, key):
        if 'public_key' in key:
            pass  # TODO must import this key
        return key['name']

    def prepare_networks(self, networks_info):
        params = []
        LOG.debug("| process networks")
        for i in range(0, len(networks_info)):
            if len(self.config['import_rules']['overwrite']['networks']) > i:
                network_info = self.config['import_rules']['overwrite']['networks'][i]
            else:
                network_info = networks_info[i]
            network = self.get_network(network_info)
            LOG.debug("| | network %s [%s]" % (network['name'], network['id']))
            port = self.quantum_client.create_port({'port': {'network_id': network['id'],
                                                             'mac_address': networks_info[i]['mac']}})['port']
            params.append({'net-id': network['id'], 'port-id': port['id']})
        return params

    def get_network(self, network_info):
        if 'id' in network_info:
            return self.quantum_client.list_networks(id=network_info['id'])['networks'][0]
        if 'name' in network_info:
            return self.quantum_client.list_networks(name=network_info['name'])['networks'][0]

    def import_instance_delta(self, data, instance, config_from):
        LOG.debug("| import instance delta")
        if instance.status == 'ACTIVE':
            print "| | instance is active. Stopping."
            instance.stop()
        LOG.debug("| | wait for instances")
        self.wait_for_status(self.nova_client.servers, instance.id, 'SHUTOFF')
        print data['disk']
        {
            'remote file': self.sync_instance_delta_remote_file
        }[data['disk']['type']](data['disk'], data['instance_name'], instance, config_from)

        instance.start()
        LOG.debug("| | sync delta: done")

    def sync_instance_delta_remote_file(self, disk_data, libvirt_name,instance, config_from):
        LOG.debug("| | sync with remote file")
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        source_instance_name = libvirt_name
        print source_instance_name
        dest_instance_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        print dest_instance_name

        LOG.debug("| | copy file")
#        subprocess.call(['eval `ssh-agent` | ssh-add'])
#        subprocess.call(['ssh', host, "scp %s:%s /var/lib/nova/instances/%s/disk" %
#                                      (disk_data['host'], disk_data['file'], instance.id)])

        with settings(host_string=config_from['host']):
            with forward_agent(env.key_filename):
                with up_ssh_tunnel(host, self.config['host']):
                    out = run(("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'") % (disk_data['host'], source_instance_name))
                    source_disk=out.split()[4]
                    out = run(("ssh -oStrictHostKeyChecking=no -p 9999 localhost 'virsh domblklist %s'") % dest_instance_name)
                    dest_disk=out.split()[4]
                    run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' " +
                        "| ssh -oStrictHostKeyChecking=no -p 9999 localhost 'dd bs=1M of=%s'") %
                        (disk_data['host'], source_disk, dest_disk))

    def import_volumes(self, data, instance):
        LOG.debug("| import volumes")
        LOG.debug("| | wait for instance activating")
        self.wait_for_status(self.nova_client.servers, instance.id, 'ACTIVE')
        for volume_info in data['volumes']:
            LOG.debug("| | | volume %s" % volume_info['name'])
            LOG.debug("| | | | creating volume")
            volume = self.cinder_client.volumes.create(size=volume_info['size'],
                                                          display_name=volume_info['name'],
                                                          display_description=volume_info['description'],
                                                          volume_type=volume_info['volume_type'],
                                                          availability_zone=volume_info['availability_zone'])
            LOG.debug("| | | | wait for available")
            self.wait_for_status(self.cinder_client.volumes, volume.id, 'available')
            LOG.debug("| | | | attach vol")
            self.nova_client.volumes.create_server_volume(instance.id, volume.id, volume_info['device'])
            LOG.debug("| | | | wait for using")
            self.wait_for_status(self.cinder_client.volumes, volume.id, 'in-use')
            LOG.debug("| | | | sync data")

            {
                'remote disk by id': self.import_volume_remote_disk_by_id
            }[volume_info['type']](volume_info, instance, volume)

            LOG.debug("| | | | done")

    def import_volume_remote_disk_by_id(self, volume_info, instance, volume):
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        subprocess.call(['ssh', volume_info['host'],
                         "dd bs=4M if=`ls /dev/disk/by-path/*%s-lun-1` | ssh %s 'dd bs=4M of=`ls /dev/disk/by-path/*%s*`'"
                         % (volume_info['id'], host, volume.id)])