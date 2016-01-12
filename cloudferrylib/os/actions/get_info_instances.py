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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils


class GetInfoInstances(action.Action):

    def run(self, **kwargs):
        search_opts = {'search_opts': kwargs.get('search_opts', {})}
        search_opts.update(kwargs.get('search_opts_tenant', {}))
        compute_resource = self.cloud.resources[utils.COMPUTE_RESOURCE]
        info = compute_resource.read_info(**search_opts)
        return {
            'info': info
        }
