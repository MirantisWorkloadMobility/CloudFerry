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
from cloudferrylib.os.actions import get_info_instances


class ConvertVolumeToCompute(action.Action):
    def __init__(self, src_cloud, dst_cloud):
        self.src_cloud = src_cloud
        self.dst_cloud = dst_cloud
        super(ConvertVolumeToCompute, self).__init__()

    def run(self, storage_info, compute_ignored={}, **kwargs):
        volume_info = copy.deepcopy(storage_info)

        new_instance_info = {'compute': {'instances': compute_ignored}}
        instances = new_instance_info['compute']['instances']

        for volume in volume_info['storage']['volumes'].itervalues():
            instance_id = volume['meta']['instance']['instance']['id']
            if instance_id not in instances:
                get_inst_info_action = get_info_instances.GetInfoInstances(
                    self.src_cloud)
                compute_info = get_inst_info_action.run(id=instance_id)['compute_info']
                instances[instance_id] = compute_info['compute']['instances'][
                    instance_id]
                instances[instance_id]['meta']['volume'] = []
            volume['meta'].pop('instance')
            instances[instance_id]['meta']['volume'].append(volume)
        return {'info': new_instance_info}
