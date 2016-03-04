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

from cloudferrylib.copy_engines import base
from cloudferrylib.utils import local
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import retrying
from cloudferrylib.utils import ssh_util

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

BBCP_PATH = '/usr/local/bin/bbcp'


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

        tmp_path = '/tmp/bbcp'
        if position == 'src':
            bbcp = CONF.bbcp.src_path
            user = CONF.src.ssh_user
        else:
            bbcp = CONF.bbcp.dst_path
            user = CONF.dst.ssh_user

        LOG.debug("Copying %s to %s:/usr/local/bin/bbcp", bbcp, host)
        cmd = "scp {cipher} -o {opts} {bbcp} {user}@{host}:{tmp}"
        local.run(cmd.format(opts='StrictHostKeyChecking=no',
                             bbcp=bbcp,
                             user=user,
                             host=host,
                             tmp=tmp_path,
                             cipher=ssh_util.get_cipher_option()),
                  capture_output=False)
        cmd = "mv {tmp} {path} && chmod 755 {path}"
        runner.run(cmd, tmp=tmp_path, path=BBCP_PATH)

    def transfer(self, data):
        src_host = data['host_src']
        src_path = data['path_src']
        dst_host = data['host_dst']
        dst_path = data['path_dst']

        options = CONF.bbcp.options
        additional_options = []
        # -f: forces the copy by first unlinking the target file before
        # copying.
        # -p: preserve source mode, ownership, and dates.
        forced_options = ['-f', '-p']
        if CONF.migrate.copy_with_md5_verification:
            # -e: error check data for transmission errors using md5 checksum.
            forced_options.append('-e')
        for o in forced_options:
            if o not in options:
                additional_options.append(o)
        # -S: command to start bbcp on the source node.
        # -T: command to start bbcp on the target node.
        for o in ('-S', '-T'):
            if o not in options:
                additional_options.append(o + " '{bbcp_cmd}'")
        bbcp_cmd = "ssh {ssh_opts} %I -l %U %H bbcp".format(
            ssh_opts=ssh_util.default_ssh_options())
        options += ' ' + ' '.join(additional_options).format(bbcp_cmd=bbcp_cmd)
        cmd = ("{bbcp} {options} "
               "{src_user}@{src_host}:{src_path} "
               "{dst_user}@{dst_host}:{dst_path} "
               "2>&1")
        retrier = retrying.Retry(
            max_attempts=CONF.migrate.retry,
            timeout=0,
        )
        try:
            retrier.run(local.run, cmd.format(bbcp=CONF.bbcp.path,
                                              options=options,
                                              src_user=CONF.src.ssh_user,
                                              dst_user=CONF.dst.ssh_user,
                                              src_host=src_host,
                                              dst_host=dst_host,
                                              src_path=src_path,
                                              dst_path=dst_path),
                        capture_output=False)
        except retrying.MaxAttemptsReached:
            self.clean_dst(data)
            raise base.FileCopyError(**data)

    def check_usage(self, data):
        LOG.debug('Checking if bbcp is available')
        if not all(os.path.isfile(p) for p in {CONF.bbcp.path,
                                               CONF.bbcp.src_path,
                                               CONF.bbcp.dst_path}):
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
