# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

from migrationlib.os import osCommon
from osBuilderExporter import osBuilderExporter

from utils import log_step, get_log

LOG = get_log(__name__)

VOLUMES_VIA_GLANCE = 'volumes_via_glance'
VOLUMES = 'volumes'

class Exporter(osCommon.osCommon):

    def __init__(self, config):

        """ config initialization"""

        self.config = config['clouds']['source']
        self.config_to = config['clouds']['destination']
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
        return {
          VOLUMES_VIA_GLANCE: lambda builder: self.__general_algorithm_export(builder).get_volumes_via_glance(),
          VOLUMES: lambda builder: self.__general_algorithm_export(builder).get_volumes()
        }[self.__config_transfer_volumes()]

    def __config_transfer_volumes(self):
        return VOLUMES if not self.config['cinder']['transfer_via_glance'] else VOLUMES_VIA_GLANCE

    def __general_algorithm_export(self, builder):
        return builder\
            .stop_instance()\
            .get_name()\
            .get_image()\
            .get_flavor()\
            .get_sec_gr_and_rules()\
            .get_metadata()\
            .get_key()\
            .get_availability_zone()\
            .get_config_drive()\
            .get_disk_config()\
            .get_networks()\
            .get_disk()\
            .get_instance_name()
