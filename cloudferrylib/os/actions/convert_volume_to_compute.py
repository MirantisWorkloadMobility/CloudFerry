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


class ConvertVolumeToCompute(action.Action):

    def run(self, storage_info, compute_ignored={}, **kwargs):
        volume_info = copy.deepcopy(storage_info)
        instances = copy.deepcopy(compute_ignored)
        new_instance_info = {'instances': instances}
        volumes_old = volume_info['volumes']
        for volume in volumes_old.itervalues():
            instance_id = volume['meta']['instance']['instance']['id']
            if instance_id not in instances:
                instances[instance_id] = volume['meta']['instance']
                instances[instance_id]['meta']['volume'] = []
            volume['meta'].pop('instance')
            instances[instance_id] = self.map_volume(instances[instance_id],
                                                     volume)
        for inst in instances.itervalues():
            for vol in inst['instance']['volumes']:
                volumes_old[vol['id']]['volume']['device'] = vol['device']
                inst['meta']['volume'].append(volumes_old[vol['id']])
        return {'info': new_instance_info}

    @staticmethod
    def map_volume(instance, volume):
        for vol_old in instance['instance']['volumes']:
            if volume['old_id'] == vol_old['id']:
                vol_old['id'] = volume['volume']['id']
        return instance
