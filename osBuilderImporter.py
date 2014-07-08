import logging
from osCommon import osCommon
from utils import forward_agent, up_ssh_tunnel, ChecksumImageInvalid
from fabric.api import run, settings, env
import time

__author__ = 'mirrorcoder'

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('importer.log')
LOG.addHandler(hdlr)


class osBuilderImporter:
    def __init__(self, glance_client, cinder_client, nova_client, quantum_client, config, config_from, data):
        self.glance_client = glance_client
        self.cinder_client = cinder_client
        self.nova_client = nova_client
        self.quantum_client = quantum_client
        self.config = config
        self.config_from = config_from
        self.data = data
        self.data_for_instance = dict()
        self.instance = object()

    def finish(self):
        LOG.info("| instance be migrated")
        return self.instance

    def prepare_for_creating_new_instance(self):
        LOG.info("| prepare env for creating new instance")
        LOG.debug("| | Get name")
        self.data_for_instance["name"] = self.data["name"]
        LOG.debug("| | Get image")
        self.data_for_instance["image"] = self.__get_image(self.data)
        LOG.debug("| | Get flavor")
        self.data_for_instance["flavor"] = self.__get_flavor(self.__ensure_param(self.data, 'flavor'))
        LOG.debug("| | Get metadata")
        self.data_for_instance["meta"] = self.__ensure_param(self.data, 'metadata')
        LOG.debug("| | Get security groups")
        self.data_for_instance["security_groups"] = self.__ensure_param(self.data, 'security_groups')
        LOG.debug("| | Get key name")
        self.data_for_instance["key_name"] = self.__get_key_name(self.__ensure_param(self.data, 'key'))
        LOG.debug("| | Get config drive")
        self.data_for_instance["config_drive"] = self.__ensure_param(self.data, 'config_drive')
        LOG.debug("| | Get disk config")
        self.data_for_instance["disk_config"] = self.__ensure_param(self.data, 'diskConfig')
        LOG.debug("| | Get nics")
        self.data_for_instance["nics"] = self.__prepare_networks(self.data['networks'])
         #availability_zone=self.ensure_param(data, 'availability_zone')
        return self

    def create_instance(self):
        LOG.info("| creating new instance")
        self.instance = self.nova_client.servers.create(**self.data_for_instance)
        LOG.info("| wait for instance activating")
        self.__wait_for_status(self.nova_client.servers, self.instance.id, 'ACTIVE')
        return self

    def import_instance_delta(self):
        LOG.info("| sync delta")
        LOG.debug("| import instance delta")
        if self.instance.status == 'ACTIVE':
            LOG.info("| | instance is active. Stopping.")
            self.instance.stop()
        LOG.debug("| | wait for instances")
        self.__wait_for_status(self.nova_client.servers, self.instance.id, 'SHUTOFF')
        {
            'remote file': self.__sync_instance_delta_remote_file
        }[self.data['disk']['type']](self.data, self.instance)
        self.instance.start()
        LOG.debug("| | sync delta: done")
        return self

    def merge_delta_and_image(self):
        LOG.info("| | copying diff for instance (ceph case)")
        self.__diff_copy(self.data['disk'],
                         self.data['instance_name'],
                         self.config['host'],
                         dest_path=self.config['temp'])
        LOG.debug("| | Starting base image downloading")
        self.__download_image_from_glance(self.data_for_instance, self.config['temp'])
        LOG.debug("| | Base image dowloaded")
        LOG.debug("| | Rebasing original diff file")
        self.__diff_rebase(self.config['temp'])
        LOG.debug("| | Diff file has been rebased")
        return self

    def __diff_copy(self, disk_data, libvirt_name, dest_host, dest_path="root"):
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                out = run("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'" %
                          (disk_data['host'], libvirt_name))
                source_disk = out.split()[4]
                run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' | " +
                    "ssh -oStrictHostKeyChecking=no %s 'dd bs=1M of=%s/disk'") %
                    (disk_data['host'], source_disk, dest_host, dest_path))

    def __download_image_from_glance(self, data_for_instance, dest_path):
        baseimage_id = data_for_instance["image"].id
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                     "--os-auth-url=http://%s:35357/v2.0 " +
                    "image-download %s > %s/baseimage") %
                    (self.config['user'],
                     self.config['password'],
                     self.config['tenant'],
                     self.config['host'],
                     baseimage_id,
                     dest_path))

    def __diff_rebase(self, dest_path):
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("cd %s && qemu-img rebase -u -b baseimage disk" % dest_path)

    def __sync_instance_delta_remote_file(self, data, instance):
        LOG.debug("| | sync with remote file")
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        source_disk = data['disk']['diff_path']
        disk_host = data['disk']['host']
        dest_instance_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        LOG.debug("| | copy file")
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                with up_ssh_tunnel(host, self.config['host']):
                    out = run("ssh -oStrictHostKeyChecking=no -p 9999 localhost 'virsh domblklist %s'" %
                              dest_instance_name)
                    dest_output = out.split()
                    dest_disk = None
                    for i in dest_output:
                        print i
                        if instance.id in i:
                            dest_disk = i
                    if not dest_disk:
                        raise NameError("Can't find suitable name of the destination disk path")
                    LOG.debug("Dest disk %s" % dest_disk)
                    run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' " +
                        "| ssh -oStrictHostKeyChecking=no -p 9999 localhost 'dd bs=1M of=%s'") %
                        (disk_host, source_disk, dest_disk))

    def import_volumes(self):
        LOG.info("| migrateVolumes")
        LOG.debug("| import volumes")
        LOG.debug("| | wait for instance activating")
        self.__wait_for_status(self.nova_client.servers, self.instance.id, 'ACTIVE')
        for volume_info in self.data['volumes']:
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
            self.__wait_for_status(self.cinder_client.volumes, volume.id, 'available')
            LOG.debug("| | | | attach vol")
            self.nova_client.volumes.create_server_volume(self.instance.id, volume.id, volume_info['device'])
            LOG.debug("| | | | wait for using")
            self.__wait_for_status(self.cinder_client.volumes, volume.id, 'in-use')
            LOG.debug("| | | | sync data")

            {
                'remote disk by id': self.__import_volume_remote_disk_by_id
            }[volume_info['type']](volume_info, self.instance, volume)

            LOG.debug("| | | | done")
        return self

    def __import_volume_remote_disk_by_id(self, volume_info, instance, volume):
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                with up_ssh_tunnel(host, self.config['host']):
                    run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=4M if=`ls /dev/disk/by-path/*%s-lun-1`' | "
                        + "ssh -oStrictHostKeyChecking=no -p 9999 localhost 'dd bs=4M of=`ls /dev/disk/by-path/*%s*`'")
                        % (volume_info['host'], volume_info['id'], volume.id))

    def __ensure_param(self, data, name, rules_name=None):
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

    def __get_image(self, data):
        checksum = data["image"]["checksum"]
        for image in self.glance_client.images.list():
            if image.checksum == checksum:
                return image
        LOG.debug("Data image = %s", data)
        keystone_client_from = osCommon.get_keystone_client(self.config_from)
        glance_client_from = osCommon.get_glance_client(keystone_client_from)
        pointer_file = glance_client_from.images.data(data["image"]["id"])._resp
        image_dest = self.glance_client.images.create(name=data["image"]["name"] + "Migrate",
                                                      container_format=data["image"]["container_format"],
                                                      disk_format=data["image"]["disk_format"],
                                                      is_public=data["image"]["is_public"],
                                                      protected=data["image"]["protected"],
                                                      data=pointer_file,
                                                      size=data["image"]["size"])
        LOG.debug("image data = %s", image_dest)
        if image_dest.checksum != checksum:
            LOG.error("Checksums is not equ")
            raise ChecksumImageInvalid(checksum, image_dest.checksum)
        return image_dest

    def __get_flavor(self, flavor_info):
        if 'id' in flavor_info:
            return self.nova_client.flavors.get(flavor_info['id'])
        if 'name' in flavor_info:
            return self.nova_client.flavors.find(name=flavor_info['name'])

    def __get_key_name(self, key):
        if 'public_key' in key:
            pass  # TODO must import this key
        return key['name']

    def __prepare_networks(self, networks_info):
        params = []
        LOG.debug("| process networks")
        for i in range(0, len(networks_info)):
            if len(self.config['import_rules']['overwrite']['networks']) > i:
                network_info = self.config['import_rules']['overwrite']['networks'][i]
            else:
                network_info = networks_info[i]
            network = self.__get_network(network_info)
            LOG.debug("| | network %s [%s]" % (network['name'], network['id']))
            for item in self.quantum_client.list_ports(fields=['network_id', 'mac_address', 'id'])['ports']:
                if (item['network_id'] == network['id']) and (item['mac_address'] == networks_info[i]['mac']):
                    LOG.warn("Port with network_id exists after prev run of script %s" % item)
                    LOG.warn("and will be delete")
                    self.quantum_client.delete_port(item['id'])
            port = self.quantum_client.create_port({'port': {'network_id': network['id'],
                                                             'mac_address': networks_info[i]['mac']}})['port']
            params.append({'net-id': network['id'], 'port-id': port['id']})
        return params

    def __get_network(self, network_info):
        if 'id' in network_info:
            return self.quantum_client.list_networks(id=network_info['id'])['networks'][0]
        if 'name' in network_info:
            return self.quantum_client.list_networks(name=network_info['name'])['networks'][0]

    def __wait_for_status(self, getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)