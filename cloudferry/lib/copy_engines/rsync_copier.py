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

from cloudferry.lib.copy_engines import base
from cloudferry.lib.utils import remote_runner
from cloudferry.lib.utils import ssh_util

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class RsyncRemoteTunnelOptions(remote_runner.RemoteTunnelOptions):
    def __init__(self, host):
        super(RsyncRemoteTunnelOptions, self).__init__(
            remote_port=CONF.rsync.port,
            port=22,
            host=host
        )


class RsyncCopier(base.BaseCopier):
    """Uses `rsync` to copy files. Used by ephemeral drive copy process"""

    name = 'rsync'

    def transfer(self, data):
        host_src = data['host_src']
        path_src = data['path_src']
        host_dst = data['host_dst']
        path_dst = data['path_dst']

        cmd = ("rsync "
               "--partial "
               "--inplace "
               "--perms "
               "--times "
               "--compress "
               "--verbose "
               "--progress "
               "--rsh='ssh {ssh_opts}' "
               "{path_src} "
               "{user_dst}@{host_dst}:{path_dst}")
        ssh_opts = ssh_util.default_ssh_options()

        if CONF.migrate.direct_transfer:
            remote_tunnel = None
        else:
            ssh_opts += " -p {port}".format(port=CONF.rsync.port)
            remote_tunnel = RsyncRemoteTunnelOptions(host_dst)
            host_dst = "localhost"

        runner = self.runner(host_src, 'src', data.get('gateway'),
                             remote_tunnel=remote_tunnel)
        try:
            runner.run_repeat_on_errors(cmd,
                                        ssh_opts=ssh_opts,
                                        path_src=path_src,
                                        user_dst=CONF.dst.ssh_user,
                                        host_dst=host_dst,
                                        path_dst=path_dst)
        except remote_runner.RemoteExecutionError:
            self.clean_dst(host_dst, path_dst)
            raise base.FileCopyError(**data)

    def check_usage(self, data):
        runner = self.runner(data['host_src'], 'src')
        LOG.debug("Checking if rsync is installed")
        try:
            runner.run("rsync --help &>/dev/null")
            return True
        except remote_runner.RemoteExecutionError:
            return False
