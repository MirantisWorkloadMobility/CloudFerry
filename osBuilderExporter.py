import logging
from utils import forward_agent
from fabric.api import run, settings, env
from osVolumeTransfer import VolumeTransfer
from osImageTransfer import ImageTransfer
import time

__author__ = 'mirrorcoder'

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('exporter.log')
LOG.addHandler(hdlr)


class osBuilderExporter:
    def __init__(self, glance_client, cinder_client, nova_client, quantum_client, instance, config):
        self.glance_client = glance_client
        self.cinder_client = cinder_client
        self.nova_client = nova_client
        self.quantum_client = quantum_client
        self.data = dict()
        self.instance = instance
        self.config = config

    def finish(self):
        return self.data

    def get_name(self):
        self.data['name'] = getattr(self.instance, 'name')
        return self

    def get_metadata(self):
        self.data['metadata'] = getattr(self.instance, 'metadata')
        return self

    def get_availability_zone(self):
        self.data['availability_zone'] = getattr(self.instance, 'OS-EXT-AZ:availability_zone')
        return self

    def get_config_drive(self):
        self.data['config_drive'] = getattr(self.instance, 'config_drive')
        return self

    def get_disk_config(self):
        self.data['disk_config'] = getattr(self.instance, 'OS-DCF:diskConfig')
        return self

    def get_instance_name(self):
        self.data['instance_name'] = getattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name')
        return self

    def get_image(self):
        self.data['image'] = ImageTransfer(self.instance.image['id'], self.glance_client)
        return self

    def get_flavor(self):
        self.data['flavor'] = {'name': self.nova_client.flavors.get(self.instance.flavor['id']).name}
        return self

    def get_security_groups(self):
        self.data['security_groups'] = [security_group['name'] for security_group in self.instance.security_groups]
        return self

    def get_key(self):
        self.data['key'] = {'name': self.instance.key_name}
        return self

    def get_networks(self):
        networks = []

        for network in self.instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': self.__get_mac_by_ip(network[1][0])
            })

        self.data['networks'] = networks
        return self

    def get_disk(self):
        self.data['disk'] = {
            'type': 'remote file',
            'host': getattr(self.instance, 'OS-EXT-SRV-ATTR:host'),
            'diff_path': self.__get_instance_diff_path(self.instance)
        }
        return self

    def get_volumes(self):
        images_from_volumes = []
        print "---- volumes ----"
        print self.nova_client.volumes.get_server_volumes(self.instance.id)
        for volume_info in self.nova_client.volumes.get_server_volumes(self.instance.id):
            print "volume_info -------- ", volume_info
            volume = self.cinder_client.volumes.get(volume_info.volumeId)
            LOG.debug("| | uploading volume %s [%s] to image service" % (volume.display_name, volume.id))
            resp, image = self.cinder_client.volumes.upload_to_image(volume=volume,
                                                                     force=True,
                                                                     image_name=volume.id,
                                                                     container_format="bare",
                                                                     disk_format=self.config['cinder']['disk_format'])
            image_upload = image['os-volume_upload_image']
            self.__wait_for_status(self.glance_client.images, image_upload['image_id'], 'active')
            print "--------------- volume -----------"
            print volume.__dict__
            print "------------------- image_upload ---------------"
            print image_upload
            images_from_volumes.append(VolumeTransfer(volume,
                                                      self.instance,
                                                      image_upload['image_id'],
                                                      self.glance_client))
        self.data['volumes'] = images_from_volumes
        return self

    def __get_instance_diff_path(self, instance):
        disk_host = getattr(self.instance, 'OS-EXT-SRV-ATTR:host')
        libvirt_name = getattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name')
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                out = run("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'" %
                          (disk_host, libvirt_name))
                source_out = out.split()
                source_disk = None
                for i in source_out:
                    if instance.id in i:
                        source_disk = i
                if not source_disk:
                    raise NameError("Can't find suitable name of the source disk path")
        return source_disk

    def __get_mac_by_ip(self, ip_address):
        for port in self.port_list:
            if port["fixed_ips"][0]["ip_address"] == ip_address:
                return port["mac_address"]

    def __wait_for_status(self, getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)

    def __getattr__(self, item):
        getter = {
            'port_list': lambda: self.quantum_client.list_ports()["ports"]
        }[item]

        if getter is None:
            raise AttributeError("Exporter has no attribute %s" % item)

        return getter()