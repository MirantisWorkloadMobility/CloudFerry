import logging

__author__ = 'mirrorcoder'

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('exporter.log')
LOG.addHandler(hdlr)


class osBuilderExporter:
    def __init__(self, glance_client, cinder_client, nova_client, quantum_client, instance):
        self.glance_client = glance_client
        self.cinder_client = cinder_client
        self.nova_client = nova_client
        self.quantum_client = quantum_client
        self.data = dict()
        self.instance = instance

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
        self.data['image'] = self.glance_client.images.get(self.instance.image['id']).__dict__
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
        }
        return self

    def get_volumes(self):
        volumes = []
        for volumeInfo in self.nova_client.volumes.get_server_volumes(self.instance.id):
            volume = self.cinder_client.volumes.get(volumeInfo.volumeId)
            LOG.debug("| | volume %s [%s]" % (volume.display_name, volume.id))
            volumes.append({
                'type': 'remote disk by id',
                'id': volume.id,
                'size': volume.size,
                'name': volume.display_name,
                'description': volume.display_description,
                'volume_type': volume.volume_type,
                'availability_zone': volume.availability_zone,
                'device': volume.attachments[0]['device'],
                'host': getattr(self.instance, 'OS-EXT-SRV-ATTR:host')
            })
        self.data['volumes'] = volumes
        return self

    def __get_mac_by_ip(self, ip_address):
        for port in self.port_list:
            if port["fixed_ips"][0]["ip_address"] == ip_address:
                return port["mac_address"]

    def __getattr__(self, item):
        getter = {
            'port_list': lambda: self.quantum_client.list_ports()["ports"]
        }[item]

        if getter is None:
            raise AttributeError("Exporter has no attribute %s" % item)

        return getter()