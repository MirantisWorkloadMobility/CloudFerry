import osCommon
import subprocess
import logging
from utils import forward_agent, up_ssh_tunnel
from fabric.api import run, settings, env
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('importer.log')
LOG.addHandler(hdlr)


class Importer(osCommon.osCommon):
    def __init__(self, config):
        self.config = config['clouds']['to']
        self.config_from = config['clouds']['from']
        super(Importer, self).__init__(self.config)

    def upload(self, data):
        LOG.info("Start migrate instance")
        LOG.info("| prepare env for creating new instance")
        data_for_instance = self.prepare_for_creating_new_instance(data)
        LOG.info("| creating new instance")
        new_instance = self.create_instance(data_for_instance)
        LOG.info("| wait for instance activating")
        self.wait_for_status(self.nova_client.servers, new_instance.id, 'ACTIVE')
        LOG.info("| sync delta")
        self.import_instance_delta(data, new_instance)
        LOG.info("| migrateVolumes")
        self.import_volumes(data, new_instance)

    def prepare_for_creating_new_instance(self, data):
        data_for_instance = {}
        LOG.debug("| | Get name")
        data_for_instance["name"] = data["name"]
        LOG.debug("| | Get image")
        data_for_instance["image"] = self.get_image(data)
        LOG.debug("| | Get flavor")
        data_for_instance["flavor"] = self.get_flavor(self.ensure_param(data, 'flavor'))
        LOG.debug("| | Get metadata")
        data_for_instance["meta"] = self.ensure_param(data, 'metadata')
        LOG.debug("| | Get security groups")
        data_for_instance["security_groups"] = self.ensure_param(data, 'security_groups')
        LOG.debug("| | Get key name")
        data_for_instance["key_name"] = self.get_key_name(self.ensure_param(data, 'key'))
        LOG.debug("| | Get nics")
        data_for_instance["nics"] = self.prepare_networks(data['networks'])
        LOG.debug("| | Get config drive")
        data_for_instance["config_drive"] = self.ensure_param(data, 'config_drive')
        LOG.debug("| | Get disk config")
        data_for_instance["disk_config"] = self.ensure_param(data, 'diskConfig')
         #availability_zone=self.ensure_param(data, 'availability_zone')
        return data_for_instance

    def create_instance(self, data_for_instance):
        return self.nova_client.servers.create(**data_for_instance)

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

    def get_image(self, data):
        checksum = data["image"]["checksum"]
        for image in self.glance_client.images.list():
            if image.checksum == checksum:
                return image
        LOG.debug("Data image = %s", data)
        image_dest = self.glance_client.images.create(name=data["image"]["name"] + "Migrate",
                                                      container_format=data["image"]["container_format"],
                                                      disk_format=data["image"]["disk_format"],
                                                      visibility=data["image"]["visibility"],
                                                      protected=data["image"]["protected"])
        keystone_client_from = self.get_keystone_client(self.config_from)
        glance_client_from = self.get_glance_client(keystone_client_from)
        pointer_file = glance_client_from.images.data(data["image"]["id"])._resp
        self.glance_client.images.upload(image_dest["id"], pointer_file)
        # TODO: Add check checksum image on destination
        return self.nova_client.images.get(image_dest.id)

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

    def import_instance_delta(self, data, instance):
        LOG.debug("| import instance delta")
        if instance.status == 'ACTIVE':
            LOG.info("| | instance is active. Stopping.")
            instance.stop()
        LOG.debug("| | wait for instances")
        self.wait_for_status(self.nova_client.servers, instance.id, 'SHUTOFF')

        {
            'remote file': self.sync_instance_delta_remote_file
        }[data['disk']['type']](data['disk'], data['instance_name'], instance)

        instance.start()
        LOG.debug("| | sync delta: done")

    def sync_instance_delta_remote_file(self, disk_data, libvirt_name,instance):
        LOG.debug("| | sync with remote file")
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        source_instance_name = libvirt_name
        dest_instance_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        LOG.debug("| | copy file")
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                with up_ssh_tunnel(host, self.config['host']):
                    out = run("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'" %
                              (disk_data['host'], source_instance_name))
                    source_disk = out.split()[4]
                    out = run("ssh -oStrictHostKeyChecking=no -p 9999 localhost 'virsh domblklist %s'" %
                              dest_instance_name)
                    dest_disk = out.split()[4]
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
            if volume_info['volume_type'] == u'None':
                volume_info['volume_type'] = None
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
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                with up_ssh_tunnel(host, self.config['host']):
                    run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=4M if=`ls /dev/disk/by-path/*%s-lun-1`' | "
                        + "ssh -oStrictHostKeyChecking=no -p 9999 localhost 'dd bs=4M of=`ls /dev/disk/by-path/*%s*`'")
                        % (volume_info['host'], volume_info['id'], volume.id))
