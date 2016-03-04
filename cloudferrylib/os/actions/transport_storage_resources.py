# Copyright (c) 2016 Mirantis Inc.
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
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)


class TransportStorageResources(action.Action):
    """This action is for transporting cinders'
    resources(still quotas) from src on dst.

    Process:
     1. Read info about resources
     2. Deploy resources on dst.

     No specific config parameters.
     No dependence on other actions.
     No dependence in other actions.
    """
    def run(self, **kwargs):
        target = 'resources'
        search_opts = {'target': target}
        search_opts.update(kwargs.get('search_opts_tenant', {}))

        src_storage = self.src_cloud.resources[utl.STORAGE_RESOURCE]
        dst_storage = self.dst_cloud.resources[utl.STORAGE_RESOURCE]

        info_res = src_storage.read_info(**search_opts)
        dst_storage.deploy(info_res, target)

        return {
        }
