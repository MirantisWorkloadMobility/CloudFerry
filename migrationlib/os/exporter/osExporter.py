from migrationlib.os import osCommon
from osBuilderExporter import osBuilderExporter

from utils import log_step, get_log

LOG = get_log(__name__)


class Exporter(osCommon.osCommon):

    def __init__(self, config):

        """ config initialization"""

        self.config = config['clouds']['from']
        self.config_to = config['clouds']['to']
        super(Exporter, self).__init__(self.config)

    @log_step(LOG)
    def find_instances(self, search_opts):
        return self.nova_client.servers.list(search_opts=search_opts)

    @log_step(LOG)
    def export(self, instance):

        """
        The main method for gathering and exporting information from source cloud
        """
        builder = osBuilderExporter(self.glance_client,
                                    self.cinder_client,
                                    self.nova_client,
                                    self.network_client,
                                    instance,
                                    self.config)
        return self.get_algorithm_export()(builder)

    def get_algorithm_export(self):
        return self.__algorithm_export

    def __algorithm_export(self, builder):
        return builder\
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
            .get_volumes()
