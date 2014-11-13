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

import cmd_cfg
import ssh_util


class QemuImg(ssh_util.SshUtil):
    commit_cmd = cmd_cfg.qemu_img_cmd("commit %s")
    commit_cd_cmd = cmd_cfg.cd_cmd & commit_cmd
    convert_cmd = cmd_cfg.qemu_img_cmd("convert %s")
    convert_full_image_cmd = cmd_cfg.cd_cmd & convert_cmd("-f %s -O %s %s %s")
    backing_file_cmd = cmd_cfg.qemu_img_cmd("info %s") >> cmd_cfg.grep_cmd("\"backing file\"")
    rebase_cmd = cmd_cfg.qemu_img_cmd("rebase -u -b %s %s")
    convert_cmd = convert_cmd("-O %s %s %s")

    def diff_commit(self, dest_path, filename="disk", host_compute=None):
        cmd = self.commit_cmd(dest_path, filename)
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
        return self.execute(cmd1, host_compute), \
               self.execute(cmd2, host_compute)

    def detect_backing_file(self, dest_disk_ephemeral, host_instance):
        cmd = self.backing_file_cmd(dest_disk_ephemeral)
        return self.parsing_output_backing(self.execute(cmd, host_instance))

    @staticmethod
    def parsing_output_backing(output):
        out = output.split('\n')
        backing_file = ""
        for i in out:
            line_out = i.split(":")
            if line_out[0] == "backing file":
                backing_file = line_out[1].replace(" ", "")
        return backing_file

    def diff_rebase(self, baseimage, disk, host_compute=None):
        cmd = self.rebase_cmd(baseimage, disk)
        return self.execute(cmd, host_compute)

    # example source_path = rbd:compute/QWEQWE-QWE231-QWEWQ
    def convert(self, format_to, source_path, dest_path, host_compute=None):
        cmd = self.convert_cmd(format_to, source_path, dest_path)
        return self.execute(cmd, host_compute)
