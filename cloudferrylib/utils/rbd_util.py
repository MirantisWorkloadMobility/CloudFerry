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

__author__ = 'mirrorcoder'
import ssh_util
import cmd_cfg


class RbdUtil(ssh_util.SshUtil):
    rbd_rm_cmd = cmd_cfg.rbd_cmd("rm -p %s %s")
    rbd_import_cmd = cmd_cfg.rbd_cmd("import --image-format=%s %s %s/%s")
    rbd_export_cmd = cmd_cfg.rbd_cmd("export -p %s %s %s")
    rbd_info_cmd = cmd_cfg.rbd_cmd("-p %s info %s --format %s")

    #exmaple pool=compute filename = %s_disk.local % instane_id
    def rm(self, pool, filename, host_compute=None):
        cmd = self.rbd_rm_cmd(pool, filename)
        return self.execute(cmd, host_compute)

    #example image-format=2 output="-" pool=compute filename=%s_disk.local
    def rbd_import(self, image_format, output, pool, filename, host_compute=None):
        cmd = self.rbd_import_cmd(image_format, output, pool, filename)
        return self.execute(cmd, host_compute)

    #example pool=volume filename=volume-id1 output=-
    def rbd_export(self, pool, filename, output, host_compute=None):
        cmd = self.rbd_export_cmd(pool, filename, output)
        return self.execute(cmd, host_compute)

    #pool=images filename=image_id format=json
    def rbd_get_info(self, pool, filename, format_output='json', host_compute=None):
        cmd = self.rbd_info_cmd(pool, filename, format_output)
        return self.execute(cmd, host_compute)
