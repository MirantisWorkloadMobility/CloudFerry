# Copyright 2015 Mirantis Inc.
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

from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.utils import utils as utl

LOG = utl.get_log(__name__)


def check(os_api_call, os_api_type, position):
    try:
        LOG.info("Checking %s APIs availability on %s.",
                 os_api_type, position.upper())
        os_api_call()
    except Exception as e:
        message = ('{os_api_type} APIs on {position} check failed with: '
                   '"{msg}". Check your configuration.').format(
            os_api_type=os_api_type, msg=e.message, position=position.upper())
        LOG.error(message)
        raise exception.AbortMigrationError(message)


class CheckImageBackend(action.Action):
    def run(self, **kwargs):
        """Check image backend by getting list of images."""
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        check(image_resource.glance_client.images.list, 'Glance',
              self.cloud.position)


class CheckComputeBackend(action.Action):
    def run(self, **kwargs):
        """Check compute backend by getting instances list."""
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        check(compute_resource.nova_client.servers.list, 'Nova',
              self.cloud.position)


class CheckStorageBackend(action.Action):
    def run(self, **kwargs):
        """Check storage backend by getting volumes list."""
        storage_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        check(storage_resource.cinder_client.volumes.list, 'Cinder',
              self.cloud.position)


class CheckNetworkingAPIs(action.Action):
    def run(self, **kwargs):
        """Check networking backend by getting network list."""
        neutron = self.cloud.resources[utl.NETWORK_RESOURCE]
        check(neutron.neutron_client.list_networks, 'Neutron',
              self.cloud.position)
