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
import copy


OLD_ID = 'old_id'


class DeployVolumes(action.Action):

    def run(self, storage_info={}, identity_info={}, **kwargs):
        storage_info = copy.deepcopy(storage_info)
        deploy_info = copy.deepcopy(storage_info)
        deploy_info.update(identity_info)
        storage_info.update(identity_info)
        volume_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        new_ids = volume_resource.deploy(deploy_info)
        storage_info_new = {
            utl.VOLUMES_TYPE:
                {

                }
        }
        volumes = storage_info_new[utl.VOLUMES_TYPE]
        for new_id, old_id in new_ids.iteritems():
            volume = volume_resource.read_info(id=new_id)
            volume[utl.VOLUMES_TYPE][new_id][OLD_ID] = old_id
            volume[utl.VOLUMES_TYPE][new_id]['snapshots'] = \
                storage_info[utl.VOLUMES_TYPE][old_id]['snapshots']
            volume[utl.VOLUMES_TYPE][new_id][utl.META_INFO] = \
                storage_info[utl.VOLUMES_TYPE][old_id][utl.META_INFO]
            volumes.update(volume[utl.VOLUMES_TYPE])
        return {
            'storage_info': storage_info_new
        }
