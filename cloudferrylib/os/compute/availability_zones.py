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

import logging
import yaml

from novaclient import exceptions

from cloudferrylib.utils import proxy_client

LOG = logging.getLogger(__name__)


class AvailabilityZoneMapper(object):
    def __init__(self, nova_client, az_map_stream):
        self.nova_client = nova_client
        self.az_map = yaml.load(az_map_stream)

    @classmethod
    def from_filename(cls, nova_client, az_map_filename):
        with open(az_map_filename) as f:
            return cls(nova_client, f)

    def get_availability_zone(self, az_name):
        if az_name is None:
            return None
        try:
            with proxy_client.expect_exception(exceptions.NotFound):
                self.nova_client.availability_zones.find(zoneName=az_name)
            return az_name
        except exceptions.NotFound:
            LOG.info("Availability zone '%s' not found, picking one from "
                     "mapping config", az_name)
            return self.az_map.get(az_name) or self.az_map.get('$$default')
