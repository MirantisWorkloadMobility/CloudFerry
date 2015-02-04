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
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils import utils as utl
import copy


OLD_ID = 'old_id'


class DeploySnapshots(action.Action):

    def run(self, storage_info=None, identity_info=None, **kwargs):
        storage_info = copy.deepcopy(storage_info)
        deploy_info = copy.deepcopy(storage_info)
        deploy_info.update(identity_info)
        storage_info.update(identity_info)
        volume_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        for vol in deploy_info[utl.VOLUMES_TYPE].values():
            if vol['snapshots']:
                snapshots_time_list = []
                for snap in vol['snapshots']:
                    if len(snapshots_time_list) == 0:
                        snapshots_time_list.append(snap)
                    else:
                        pass





