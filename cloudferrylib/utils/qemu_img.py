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

import abc
import json

from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import log
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import ssh_util

LOG = log.getLogger(__name__)


class QemuImgInfoParser(object):
    """Parses `qemu-img info` command human-readable output.

    Tested on qemu-img v1.0 and v2.0.0.

    More recent versions of qemu-img support JSON output, but many real-world
    systems with old openstack releases still come with qemu-img v1.0 which
    does not support JSON"""

    __metaclass__ = abc.ABCMeta

    def __init__(self, img_info_output):
        self.info = self.parse(img_info_output)

    @abc.abstractmethod
    def parse(self, img_info_output):
        pass

    @property
    def backing_filename(self):
        return self.info.get('backing-filename')

    @property
    def format(self):
        return self.info.get('format')


class TextQemuImgInfoParser(QemuImgInfoParser):
    def parse(self, img_info_output):
        """Returns dictionary based on human-readable output from
        `qemu-img info`

        Known problem: breaks if path contains opening parenthesis `(` or
        colon `:`"""
        result = {}
        for l in img_info_output.split('\n'):
            if not l.strip():
                continue
            try:
                name, value = l.split(':', 1)
            except ValueError:
                continue
            name = name.strip()
            if name == 'backing file':
                file_end = value.find('(')
                if file_end == -1:
                    file_end = len(value)
                result['backing-filename'] = value[:file_end].strip()
            elif name == 'file format':
                result['format'] = value.strip()
        return result


class JsonQemuImgInfoParser(QemuImgInfoParser):
    def parse(self, img_info_output):
        try:
            return json.loads(img_info_output)
        except TypeError:
            LOG.debug('Unable to convert json data: %s', img_info_output)
            return {}


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

    def get_info(self, dest_disk_ephemeral, host_instance):
        try:
            # try to use JSON first, cause it's more reliable
            cmd = "qemu-img info --output=json {ephemeral}".format(
                ephemeral=dest_disk_ephemeral)
            qemu_img_json = self.execute(cmd=cmd,
                                         host_exec=host_instance,
                                         ignore_errors=False,
                                         sudo=True)
            return JsonQemuImgInfoParser(qemu_img_json)
        except remote_runner.RemoteExecutionError:
            # old qemu version not supporting JSON, fallback to human-readable
            # qemu-img output parser
            cmd = "qemu-img info {ephemeral}".format(
                ephemeral=dest_disk_ephemeral)
            qemu_img_output = self.execute(cmd=cmd,
                                           host_exec=host_instance,
                                           ignore_errors=True,
                                           sudo=True)
            return TextQemuImgInfoParser(qemu_img_output)

    def detect_backing_file(self, dest_disk_ephemeral, host_instance):
        return self.get_info(dest_disk_ephemeral,
                             host_instance).backing_filename

    def diff_rebase(self, baseimage, disk, host_compute=None):
        cmd = self.rebase_cmd(baseimage, disk)
        return self.execute(cmd, host_compute, sudo=True)

    # example source_path = rbd:compute/QWEQWE-QWE231-QWEWQ
    def convert(self, format_to, source_path, dest_path, host_compute=None):
        cmd = self.convert_cmd(format_to, source_path, dest_path)
        return self.execute(cmd, host_compute)
