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
from cloudferrylib.utils import utils as utl


class GetInfoInstances(action.Action):
    def __init__(self, init, cloud=None, search_opts=dict()):
        super(GetInfoInstances, self).__init__(init, cloud)
        self.search_opts = search_opts

    def run(self, **kwargs):
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        info = compute_resource.read_info(**self.search_opts)
        return {
            'info': info
        }
