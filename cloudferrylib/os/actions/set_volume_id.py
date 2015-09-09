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
import copy


class SetVolumeId(action.Action):

    """
    This action works with instance and must be used after GetInfoIter action
    Takes all information about attached volumes and put it in meta section
    You can use it in case when you have one volume backend for src and dst
    """

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        for instance in info['instances'].values():
            meta_volume_array = []
            for volume in instance['instance']['volumes']:
                meta_volume_array.append({'volume': volume})
            instance['meta'].update({'volume': meta_volume_array})
        return {'info': info}
