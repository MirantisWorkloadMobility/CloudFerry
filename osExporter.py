import osCommon
import logging

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('exporter.log')
LOG.addHandler(hdlr)


class Exporter(osCommon.osCommon):

    def __init__(self, config):
        self.config = config['clouds']['from']
        self.config_to = config['clouds']['to']
        super(Exporter, self).__init__(self.config)

    def find_instances(self, search_opts):
        return self.nova_client.servers.list(search_opts=search_opts)

    def export(self, instance):
        LOG.info("Exporting instance %s [%s]" % (instance.name, instance.id))
        data = dict()
        data['name'] = getattr(instance, 'name')
        data['image'] = self.get_image(instance)
        data['flavor'] = self.get_flavor(instance)
        data['security_groups'] = self.get_security_groups(instance)
        data['metadata'] = getattr(instance, 'metadata')
        data['key'] = self.get_key(instance)
        data['availability_zone'] = getattr(instance, 'OS-EXT-AZ:availability_zone'),
        data['config_drive'] = getattr(instance, 'config_drive')
        data['disk_config'] = getattr(instance, 'OS-DCF:diskConfig')
        data['networks'] = self.export_networks(instance)
        data['disk'] = self.export_disk(instance)
        data['instance_name'] = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        data['volumes'] = self.export_volumes(instance)
        return data

    def get_image(self, instance):
        return self.glance_client.images.get(instance.image['id']).__dict__

    def get_flavor(self, instance):
        return {'name': self.nova_client.flavors.get(instance.flavor['id']).name}

    def get_security_groups(self, instance):
        return [security_group['name'] for security_group in instance.security_groups]

    def get_key(self, instance):
        return {'name': instance.key_name}

    def export_networks(self, instance):
        networks = []

        for network in instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': self.get_mac_by_ip(network[1][0])
            })

        return networks

    def export_disk(self, instance):
        return {
            'type': 'remote file',
            'host': getattr(instance, 'OS-EXT-SRV-ATTR:host'),
        }

    def export_volumes(self, instance):
        volumes = []
        for volumeInfo in self.nova_client.volumes.get_server_volumes(instance.id):
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
                'host': getattr(instance, 'OS-EXT-SRV-ATTR:host')
            })
        return volumes

    def get_instance(self, instance_info):
        if 'id' in instance_info:
            return self.nova_client.servers.get(instance_info['id'])
        if 'name' in instance_info:
            return self.nova_client.servers.list(search_opts={'name': instance_info['name']})[0]

    def get_mac_by_ip(self, ip_address):
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