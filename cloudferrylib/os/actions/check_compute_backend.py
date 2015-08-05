# Copyright (c) 2015 Mirantis Inc.
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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl

LOG = utl.get_log(__name__)


class CheckComputeBackend(action.Action):
    def run(self, **kwargs):
        """Check compute backend by getting instances list.

        """
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        try:
            instances_list = compute_resource.nova_client.servers.list()
            if instances_list:
                LOG.debug('Instances list is OK')
        except Exception as e:
            LOG.error('Instances list error')
            raise e
