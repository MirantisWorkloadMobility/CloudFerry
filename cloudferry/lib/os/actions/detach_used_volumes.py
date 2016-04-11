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


from cloudferry.lib.base.action import action
from cloudferry.lib.utils import utils as utl


class DetachVolumes(action.Action):

    def run(self, storage_info=None, **kwargs):
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        if storage_info:
            for vol_id, vol_info in storage_info[utl.VOLUMES_TYPE].iteritems():
                if 'instance' in vol_info['meta']:
                    if vol_info['meta']['instance']:
                        resource_storage.detach_volume(vol_id)
        return {}
