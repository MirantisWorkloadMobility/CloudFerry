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


from fabric.api import env
from fabric.api import settings

from cloudferrylib.os.actions import utils as action_utils

from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import rbd_util
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class SSHCephToCeph(driver_transporter.DriverTransporter):
    def transfer(self, data, snapshot=None, snapshot_type=1):
        host_src = (data.get('host_src') if data.get('host_src')
                    else self.src_cloud.getIpSsh())
        host_dst = (data.get('host_dst') if data.get('host_dst')
                    else self.dst_cloud.getIpSsh())
        with settings(host_string=host_src), utils.forward_agent(
                env.key_filename):

            rbd_import_diff = rbd_util.RbdUtil.rbd_import_diff_cmd
            ssh_cmd = cmd_cfg.ssh_cmd
            ssh_rbd_import_diff = ssh_cmd(host_dst, rbd_import_diff)

            if snapshot:
                process_params = [snapshot['name'], data['path_src'], '-', '-', data['path_dst']]
                if snapshot_type == 1:
                    rbd_export_diff = rbd_util.RbdUtil.rbd_export_diff_snap_cmd
                elif snapshot_type == 2:
                    rbd_export_diff = rbd_util.RbdUtil.rbd_export_diff_from_snap_cmd
                    process_params.insert(1, snapshot['next_snapname'])
                elif snapshot_type == 3:
                    rbd_export_diff = rbd_util.RbdUtil.rbd_export_diff_from_cmd
                else:
                    raise ValueError("Unsupported snapshot type %s", snapshot_type)
            else:
                rbd_export_diff = rbd_util.RbdUtil.rbd_export_diff_cmd
                process_params = [data['path_src'], '-', '-', data['path_dst']]

            process = rbd_export_diff >> ssh_rbd_import_diff
            process = process(*process_params)

            self.src_cloud.ssh_util.execute(process)
