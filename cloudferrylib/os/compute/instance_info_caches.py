# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import pprint

from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


class InstanceInfoCaches(object):
    """
    The data from network_info column is necessary to keep the order of
    creation of network interfaces of instances.

    """

    GET_INSTANCE_INFO = ("select * from instance_info_caches "
                         "where instance_uuid = :uuid")

    def __init__(self, nova_db_connection):
        self.conn = nova_db_connection

    def get_info_caches(self, instance_id):
        """Raw data for an instance.

        :param instance_id: ID of instance
        :return: A dictionary with raw data
        """
        return (self.conn.execute(self.GET_INSTANCE_INFO, uuid=instance_id).
                fetchone())

    def get_network_info(self, instance_id):
        """Converted json data from network_info column.

        :param instance_id: ID of instance
        :return: The dictionary with network info
        """
        return json.loads(self.get_info_caches(instance_id)['network_info'])

    def enumerate_addresses(self, instance_id):
        """Mac addresses with positions

        :param instance_id: ID of instance
        :return: Dictionary with mac address: position
        """
        network_info = self.get_network_info(instance_id)
        LOG.debug('Network info of instance %s: %s', instance_id,
                  pprint.pformat(network_info))
        return {v['address']: i for i, v in enumerate(network_info)}
