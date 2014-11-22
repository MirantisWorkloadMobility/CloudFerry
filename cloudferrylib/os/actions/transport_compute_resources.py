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


import copy

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class TransportComputeResources(action.Action):
    def __init__(self, src_cloud, dst_cloud):
        self.src_cloud = src_cloud
        self.dst_cloud = dst_cloud
        super(TransportComputeResources, self).__init__()

    def run(self, info=None, **kwargs):
        instances_info = copy.deepcopy(kwargs['compute_info'])

        src_compute = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        dst_compute = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]

        info = src_compute.read_info_resources()
        new_info = dst_compute.deploy_resources(info)
        new_info[utl.COMPUTE_RESOURCE].update(
            instances_info[utl.COMPUTE_RESOURCE])

        return {
            'info': new_info
        }
