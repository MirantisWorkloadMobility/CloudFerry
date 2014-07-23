import osCommon
import logging
from osBuilderExporter import osBuilderExporter

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('migrate.log')
LOG.addHandler(hdlr)


class Exporter(osCommon.osCommon):

    def __init__(self, config):

        """ config initialization"""

        self.config = config['clouds']['from']
        self.config_to = config['clouds']['to']
        super(Exporter, self).__init__(self.config)

    def find_instances(self, search_opts):
        return self.nova_client.servers.list(search_opts=search_opts)

    def export(self, instance):

        """
        The main method for gathering and exporting information from source cloud
        """

        LOG.info("Exporting instance %s [%s]" % (instance.name, instance.id))
        data = osBuilderExporter(self.glance_client,
                                 self.cinder_client,
                                 self.nova_client,
                                 self.network_client,
                                 instance,
                                 self.config)\
            .stop_instance()\
            .get_name()\
            .get_image()\
            .get_flavor()\
            .get_security_groups()\
            .get_metadata()\
            .get_key()\
            .get_availability_zone()\
            .get_config_drive()\
            .get_disk_config()\
            .get_networks()\
            .get_disk()\
            .get_instance_name()\
            .get_volumes()\
            .finish()
        print "------------------data--------------------", data
        return data
