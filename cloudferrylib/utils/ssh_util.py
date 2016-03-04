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

from oslo_config import cfg

from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import utils

CONF = cfg.CONF


class SshUtil(object):
    def __init__(self, cloud, config_migrate, host=None):
        self.cloud = cloud
        self.host = host or self.cloud.ssh_host
        self.config_migrate = config_migrate

    def execute(self, cmd, internal_host=None, host_exec=None,
                ignore_errors=False, sudo=False):
        host = host_exec if host_exec else self.host
        runner = \
            remote_runner.RemoteRunner(host,
                                       self.cloud.ssh_user,
                                       password=self.cloud.ssh_sudo_password,
                                       sudo=sudo,
                                       ignore_errors=ignore_errors)
        if internal_host:
            return self.execute_on_inthost(runner, str(cmd), internal_host)
        else:
            return runner.run(str(cmd))

    def execute_on_inthost(self, runner, cmd, host):
        with utils.forward_agent(self.config_migrate.key_filename):
            return runner.run(str(cmd_cfg.ssh_cmd(host, str(cmd))))


def get_cipher_option():
    if CONF.migrate.ssh_cipher:
        return '-c ' + CONF.migrate.ssh_cipher
    else:
        return ''


def default_ssh_options():
    options = [
        '-o UserKnownHostsFile=/dev/null',
        '-o StrictHostKeyChecking=no'
    ]
    return ' '.join(options)
