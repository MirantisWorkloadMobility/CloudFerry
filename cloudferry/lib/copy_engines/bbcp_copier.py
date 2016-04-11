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
import os

from oslo_config import cfg

from cloudferry.lib.copy_engines import base
from cloudferry.lib.utils import local
from cloudferry.lib.utils import remote_runner
from cloudferry.lib.utils import retrying
from cloudferry.lib.utils import ssh_util

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

BBCP_PATH = '/tmp/bbcp'


class BbcpCopier(base.BaseCopier):
    """
    BBCP extension allows using the bbcp to transfer files beeetwen nodes.
    """

    name = 'bbcp'

    def copy_bbcp(self, host, position):
        """
        Check that the bbcp is installed on the host otherwise copy bbcp to
        the host.

        :param host: Host to which the bbcp will be copied
        :param position: src or dst
        """
        runner = self.runner(host, position)

        LOG.debug("Checking if bbcp is installed on '%s' host", host)
        cmd = "bbcp --help &>/dev/null"
        try:
            runner.run(cmd)
        except remote_runner.RemoteExecutionError:
            pass
        else:
            return

        if position == 'src':
            bbcp = CONF.bbcp.src_path
            user = CONF.src.ssh_user
        else:
            bbcp = CONF.bbcp.dst_path
            user = CONF.dst.ssh_user

        LOG.debug("Copying %s to %s:%s", bbcp, host, BBCP_PATH)
        cmd = "scp {ssh_opts} {bbcp} {user}@{host}:{tmp}"
        local.run(cmd.format(ssh_opts=ssh_util.default_ssh_options(),
                             bbcp=bbcp,
                             user=user,
                             host=host,
                             tmp=BBCP_PATH),
                  capture_output=False)
        cmd = "chmod 755 {path}"
        runner.run(cmd, path=BBCP_PATH)

    def transfer(self, data):
        host_src = data['host_src']
        path_src = data['path_src']
        host_dst = data['host_dst']
        path_dst = data['path_dst']

        cmd = "{bbcp} {options} {src} {dst} 2>&1"

        options = CONF.bbcp.options
        additional_options = []
        # -f: forces the copy by first unlinking the target file before
        # copying.
        # -p: preserve source mode, ownership, and dates.
        # -S: command to start bbcp on the source node.
        # -T: command to start bbcp on the target node.
        forced_options = ['-f', '-p']
        if CONF.migrate.copy_with_md5_verification:
            # -e: error check data for transmission errors using md5 checksum.
            forced_options.append('-e')
        for o in forced_options:
            if o not in options:
                additional_options.append(o)
        run_options = ['-T']
        if CONF.migrate.direct_transfer:
            src = path_src
            bbcp = BBCP_PATH
            runner = self.runner(host_src, 'src', data.get('gateway'))
            run = runner.run
        else:
            run_options += ['-S']
            src = '{user_src}@{host_src}:{path_src}'.format(
                user_src=CONF.src.ssh_user,
                host_src=host_src,
                path_src=path_src,
            )
            bbcp = CONF.bbcp.path
            run = local.run
        dst = '{user_dst}@{host_dst}:{path_dst}'.format(
            user_dst=CONF.dst.ssh_user,
            host_dst=host_dst,
            path_dst=path_dst,
        )
        for o in run_options:
            if o not in options:
                additional_options.append(o + " '{remote_bbcp}'")
        remote_bbcp = "ssh {ssh_opts} %I -l %U %H {path}".format(
            ssh_opts=ssh_util.default_ssh_options(),
            path=BBCP_PATH
        )
        options += ' ' + ' '.join(additional_options).format(
            remote_bbcp=remote_bbcp)

        retrier = retrying.Retry(
            max_attempts=CONF.migrate.retry,
            timeout=0
        )
        try:
            retrier.run(run, cmd.format(bbcp=bbcp, options=options, src=src,
                                        dst=dst),
                        capture_output=False)
        except retrying.MaxAttemptsReached:
            self.clean_dst(host_dst, path_dst)
            raise base.FileCopyError(**data)

    def check_usage(self, data):
        LOG.debug('Checking if bbcp is available')
        path = {CONF.bbcp.path, CONF.bbcp.src_path, CONF.bbcp.dst_path}
        if not all(os.path.isfile(p) for p in path):
            LOG.error("The path of bbcp are not valid: %s", path)
            return False
        for host, position, cloud in (
                (data['host_src'], 'src', self.src_cloud),
                (data['host_dst'], 'dst', self.dst_cloud)):
            if host not in cloud.hosts_with_bbcp:
                try:
                    self.copy_bbcp(host, position)
                    cloud.hosts_with_bbcp.add(host)
                except (remote_runner.RemoteExecutionError,
                        local.LocalExecutionFailed):
                    return False
        return True


def remove_bbcp(cloud):
    """
    Remove bbcp from the hosts were memorized in the hosts_with_bbcp variable.

    :param cloud: object of a cloud
    """
    if cloud.position == 'src':
        user = CONF.src.ssh_user
        sudo_password = CONF.src.ssh_sudo_password
    else:
        user = CONF.dst.ssh_user
        sudo_password = CONF.dst.ssh_sudo_password

    LOG.info("Removing the bbcp files from hosts of '%s' cloud: %s",
             cloud.position, cloud.hosts_with_bbcp)
    cmd = 'rm -f {path}'
    for host in cloud.hosts_with_bbcp:
        runner = remote_runner.RemoteRunner(host, user, password=sudo_password,
                                            sudo=True)
        runner.run_ignoring_errors(cmd, path=BBCP_PATH)
