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


from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import ssh_util


class RbdUtil(ssh_util.SshUtil):
    rbd_rm_cmd = cmd_cfg.rbd_cmd("rm -p %s %s")
    rbd_import_cmd = cmd_cfg.rbd_cmd("import --image-format=%s %s %s")
    rbd_import_diff_cmd = cmd_cfg.rbd_cmd("import-diff %s %s")
    rbd_export_cmd = cmd_cfg.rbd_cmd("export %s %s")
    rbd_export_diff_cmd = cmd_cfg.rbd_cmd("export-diff %s %s")
    rbd_export_diff_snap_cmd = cmd_cfg.rbd_cmd("export-diff --snap %s %s %s")
    rbd_export_diff_from_snap_cmd = \
        cmd_cfg.rbd_cmd("export-diff --from-snap %s --snap %s %s %s")
    rbd_export_diff_from_cmd = \
        cmd_cfg.rbd_cmd("export-diff --from-snap %s %s %s")
    rbd_info_cmd = cmd_cfg.rbd_cmd("-p %s info %s --format %s")
    rbd_snap_rm = cmd_cfg.rbd_cmd("snap rm %s@%s")

    # exmaple pool=compute filename = %s_disk.local % instance_id
    def rm(self, pool, filename, int_host=None):
        cmd = self.rbd_rm_cmd(pool, filename)
        return self.execute(cmd, int_host)

    def snap_rm(self, volume_path, snapshot_name, int_host=None):
        cmd = self.rbd_snap_rm(volume_path, snapshot_name)
        return self.execute(cmd, int_host)

    # example image-format=2 output="-" filename=%s_disk.local
    def rbd_import(self, image_format, output, filename, int_host=None):
        cmd = self.rbd_import_cmd(image_format, output, filename)
        return self.execute(cmd, int_host)

    # example output="-" ceph_path=%s_disk.local
    def rbd_import_diff(self, output, ceph_path, int_host=None):
        cmd = self.rbd_import_cmd(output, ceph_path)
        return self.execute(cmd, int_host)

    # example filename=volume-id1 output=-
    def rbd_export(self, filename, output, int_host=None):
        cmd = self.rbd_export_cmd(filename, output)
        return self.execute(cmd, int_host)

    # example ceph_path=volume-id1 output=-
    def rbd_export_diff(self, ceph_path, output, int_host=None):
        cmd = self.rbd_export_cmd(ceph_path, output)
        return self.execute(cmd, int_host)

    # pool=images filename=image_id format=json
    def rbd_get_info(self, pool, filename, format_output='json',
                     int_host=None):
        cmd = self.rbd_info_cmd(pool, filename, format_output)
        return self.execute(cmd, int_host)
