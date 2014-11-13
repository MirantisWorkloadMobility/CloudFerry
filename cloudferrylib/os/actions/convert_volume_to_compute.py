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


class ConvertVolumeToCompute(action.Action):
    def __init__(self, cloud):
        self.cloud = cloud
        super(ConvertVolumeToCompute, self).__init__()

    def run(self, volume_info, **kwargs):

        new_instance_info = {'compute': {'instances': {}}}

        for volume in volume_info['storage']['volumes'].itervalues():
            temp_inst_info = {'compute': volume['meta'].pop('compute')}
            temp_inst_info['compute']['meta'] = volume

            new_instance_info['compute']['instances'].update(temp_inst_info['compute'])

        return {'instance_info': new_instance_info}

