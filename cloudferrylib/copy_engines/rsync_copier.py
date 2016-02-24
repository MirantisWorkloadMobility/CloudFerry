# Copyright (c) 2016 Mirantis Inc.
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

import logging

from oslo_config import cfg

from cloudferrylib.copy_engines import base
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import ssh_util

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class RsyncCopier(base.BaseCopier):
    """Uses `rsync` to copy files. Used by ephemeral drive copy process"""

    name = 'rsync'

    def transfer(self, data):
        src_host = data['host_src']
        src_path = data['path_src']
        dst_host = data['host_dst']
        dst_path = data['path_dst']
        gateway = data.get('gateway')

        cmd = ("rsync "
               "--partial "
               "--inplace "
               "--perms "
               "--times "
               "--compress "
               "--verbose "
               "--progress "
               "--rsh='ssh {ssh_opts} {ssh_cipher}' "
               "{source_file} "
               "{dst_user}@{dst_host}:{dst_path}")
        ssh_opts = " ".join(["-o {}".format(opt)
                             for opt in ["UserKnownHostsFile=/dev/null",
                                         "StrictHostKeyChecking=no"]])

        src_runner = self.runner(src_host, 'src', gateway=gateway)
        try:
            src_runner.run_repeat_on_errors(
                    cmd,
                    ssh_cipher=ssh_util.get_cipher_option(),
                    ssh_opts=ssh_opts,
                    source_file=src_path,
                    dst_user=CONF.dst.ssh_user,
                    dst_host=dst_host,
                    dst_path=dst_path)
        except remote_runner.RemoteExecutionError:
            self.clean_dst(data)
            raise base.FileCopyError(**data)

    def check_usage(self, data):
        src_host = data['host_src']
        runner = self.runner(src_host, 'src')
        LOG.debug("Checking if rsync is installed")
        try:
            runner.run("rsync --help &>/dev/null")
            return True
        except remote_runner.RemoteExecutionError:
            return False
