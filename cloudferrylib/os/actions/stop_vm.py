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
import copy


class StopVms(action.Action):
    def __init__(self, cloud):
        self.cloud = cloud
        super(StopVms, self).__init__()

    def run(self, **kwargs):
        compute_info = copy.deepcopy(kwargs['compute_info'])
        compute_resource = self.cloud.resources['compute']

        for instance in compute_info['compute']['instances']:
            compute_resource.change_status('shutoff', instance_id=instance)

        return {}
