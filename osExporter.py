import osCommon
import logging

LOG = logging.getLogger(__name__)


class Exporter(osCommon.osCommon):

    def __init__(self, config):
        super(Exporter, self).__init__(config)

    def find_instances(self, search_opts):
        return self.nova_client.servers.list(search_opts=search_opts)

    def export(self, instance):
        LOG.info("Exporting instance %s [%s]" % (instance.name, instance.id))
        data = {'name': instance.name}

        LOG.debug("| take image name")
        data['image'] = {'name': self.nova_client.images.get(instance.image['id']).name}

        LOG.debug("| take flavor name")
        data['flavor'] = {'name': self.nova_client.flavors.get(instance.flavor['id']).name}

        data['security_groups'] = [security_group['name'] for security_group in instance.security_groups]
        data['metadata'] = instance.metadata
        data['key'] = {'name': instance.key_name}
        data['availability_zone'] = getattr(instance, 'OS-EXT-AZ:availability_zone'),
        data['config_drive'] = instance.config_drive
        data['disk_config'] = getattr(instance, 'OS-DCF:diskConfig')
        data['networks'] = self.export_networks(instance)
        data['disk'] = self.export_disk(instance)
        LOG.debug("| exporting volumes")
        data['volumes'] = self.export_volumes(instance)

        return data

    def export_networks(self, instance):
        networks = []

        for network in instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': self.get_mac_by_ip(network[1][0])
            })

        return networks

    @staticmethod
    def export_disk(instance):
        return {
            'type': 'remote file',
            'host': getattr(instance, 'OS-EXT-SRV-ATTR:host'),
            'file': '/var/lib/nova/instances/%s/disk' % instance.id,
            'pattern_to': '/var/lib/nova/instances/%s/disk'
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