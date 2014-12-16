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


from fabric.api import run
from fabric.api import settings

import cmd_cfg
from utils import forward_agent


class SshUtil(object):
    def __init__(self, cloud, config_migrate):
        self.cloud = cloud
        self.host = cloud.host
        self.config_migrate = config_migrate

    def execute(self, cmd, host_compute=None, host_exec=None):
        host = host_exec if host_exec else self.host
        with settings(host_string=host):
            if host_compute:
                return self.execute_on_compute(str(cmd), host_compute)
            else:
                return run(str(cmd))

    def execute_on_compute(self, cmd, host):
        with forward_agent(self.config_migrate.key_filename):
            return run(str(cmd_cfg.ssh_cmd(host, str(cmd))))
