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

import json

from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import ssh_util
from cloudferrylib.utils import utils

LOG = utils.get_log(__name__)


class QemuImg(ssh_util.SshUtil):
    commit_cmd = cmd_cfg.qemu_img_cmd("commit %s")
    commit_cd_cmd = cmd_cfg.cd_cmd & commit_cmd
    convert_cmd = cmd_cfg.qemu_img_cmd("convert %s")
    convert_full_image_cmd = cmd_cfg.cd_cmd & convert_cmd("-f %s -O %s %s %s")
    rebase_cmd = cmd_cfg.qemu_img_cmd("rebase -u -b %s %s")
    convert_cmd = convert_cmd("-O %s %s %s")

    def diff_commit(self, dest_path, filename="disk", host_compute=None):
        cmd = self.commit_cd_cmd(dest_path, filename)
        return self.execute(cmd, host_compute)

    def convert_image(self,
                      disk_format,
                      path_to_image,
                      output_format="raw",
                      baseimage="baseimage",
                      baseimage_tmp="baseimage.tmp",
                      host_compute=None):
        cmd1 = self.convert_full_image_cmd(path_to_image,
                                           disk_format,
                                           output_format,
                                           baseimage,
                                           baseimage_tmp)
        cmd2 = cmd_cfg.move_cmd(path_to_image,
                                baseimage_tmp,
                                baseimage)
        return \
            self.execute(cmd1, host_compute), self.execute(cmd2, host_compute)

    def detect_backing_file(self, dest_disk_ephemeral, host_instance):
        cmd = "qemu-img info --output=json {ephemeral}".format(
            ephemeral=dest_disk_ephemeral)
        qemu_img_json = self.execute(cmd=cmd,
                                     host_exec=host_instance,
                                     ignore_errors=True)
        try:
            return json.loads(qemu_img_json)['backing-filename']
        except (TypeError, ValueError, KeyError) as e:
            LOG.warning("Unable to read qemu image file for '%s', error: '%s'",
                        dest_disk_ephemeral, e)

    def diff_rebase(self, baseimage, disk, host_compute=None):
        cmd = self.rebase_cmd(baseimage, disk)
        return self.execute(cmd, host_compute)

    # example source_path = rbd:compute/QWEQWE-QWE231-QWEWQ
    def convert(self, format_to, source_path, dest_path, host_compute=None):
        cmd = self.convert_cmd(format_to, source_path, dest_path)
        return self.execute(cmd, host_compute)
