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
from cloudferrylib.os.actions import snap_transfer
from cloudferrylib.utils.drivers import ssh_ceph_to_ceph
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
                snapshots_list = [snapshot_info for snapshot_info in vol['snapshots'].values()]
                snapshots_list.sort(key=lambda x: x.created_at)
                for snap in snapshots_list:
                    if snapshots_list.index(snap) == 0:
                        act_snap_transfer = snap_transfer.SnapTransfer(self.init,
                                                                       ssh_ceph_to_ceph.SSHCephToCeph, 1)
                    elif snapshots_list.index(snap) == len(vol['snapshots']) - 1:
                        act_snap_transfer = snap_transfer.SnapTransfer(self.init,
                                                                       ssh_ceph_to_ceph.SSHCephToCeph, 3)
                    else:
                        snap_num = snapshots_list.index(snap)
                        snap['next_snapname'] = snapshots_list[snap_num + 1]['name']
                        act_snap_transfer = snap_transfer.SnapTransfer(self.init,
                                                                       ssh_ceph_to_ceph.SSHCephToCeph, 2)
