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
from cloudferrylib.copy_engines import ssh_ceph_to_ceph
from cloudferrylib.os.actions import snap_transfer
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils import rbd_util
from cloudferrylib.utils import utils as utl

OLD_ID = 'old_id'


class DeployVolSnapshots(action.Action):

    def run(self, storage_info=None, identity_info=None, **kwargs):
        storage_info = copy.deepcopy(storage_info)
        deploy_info = copy.deepcopy(storage_info)
        deploy_info.update(identity_info)
        storage_info.update(identity_info)
        volume_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        for vol_id, vol in deploy_info[utl.VOLUMES_TYPE].iteritems():
            if vol['snapshots']:

                vol_info = vol[utl.VOLUME_BODY]

                snapshots_list = \
                    [snap_info for snap_info in vol['snapshots'].values()]

                snapshots_list.sort(key=lambda x: x['created_at'])

                for snap in snapshots_list:
                    if snapshots_list.index(snap) == 0:
                        act_snap_transfer = \
                            snap_transfer.SnapTransfer(
                                self.init,
                                ssh_ceph_to_ceph.SSHCephToCeph,
                                1)
                    else:
                        snap_num = snapshots_list.index(snap)
                        snap['prev_snapname'] = \
                            snapshots_list[snap_num - 1]['name']
                        act_snap_transfer = \
                            snap_transfer.SnapTransfer(
                                self.init,
                                ssh_ceph_to_ceph.SSHCephToCeph,
                                2)

                    act_snap_transfer.run(volume=vol_info, snapshot_info=snap)

                    volume_resource.create_snapshot(
                        volume_id=vol_id,
                        display_name=snap['display_name'],
                        display_description=snap['display_description'])

                act_snap_transfer = snap_transfer.SnapTransfer(
                    self.init,
                    ssh_ceph_to_ceph.SSHCephToCeph,
                    3)
                act_snap_transfer.run(volume=vol_info,
                                      snapshot_info=snapshots_list[-1])

                for snap in snapshots_list:
                    if volume_resource.config.storage.host:
                        act_delete_redundant_snap = \
                            rbd_util.RbdUtil(cloud=self.cloud,
                                             config_migrate=self.cfg.migrate,
                                             host=vol_info[utl.HOST_DST])
                        act_delete_redundant_snap.snap_rm(
                            vol_info[utl.PATH_DST],
                            snap['name'])
                    else:
                        act_delete_redundant_snap = \
                            rbd_util.RbdUtil(cloud=self.cloud,
                                             config_migrate=self.cfg.migrate)
                        act_delete_redundant_snap.snap_rm(
                            vol_info[utl.PATH_DST],
                            snap['name'], vol_info[utl.HOST_DST])

            else:
                one_volume_info = {
                    'one_volume_info': {
                        utl.VOLUMES_TYPE: {
                            vol_id: vol
                        }
                    }
                }

                act_transport_vol_data = \
                    task_transfer.TaskTransfer(self.init,
                                               'SSHCephToCeph',
                                               input_info='one_volume_info')

                act_transport_vol_data.run(**one_volume_info)

        return {}
