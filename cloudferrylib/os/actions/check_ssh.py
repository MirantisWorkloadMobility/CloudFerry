# Copyright (c) 2015 Mirantis Inc.
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


from fabric.api import settings

from cloudferrylib.base.action import action
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import utils as utl


class CheckSSH(action.Action):
    def run(self, info=None, **kwargs):
        for node in self.get_compute_nodes():
            self.check_access(node)

    def get_compute_nodes(self):
        return self.cloud.resources[utl.COMPUTE_RESOURCE].get_compute_hosts()

    def check_access(self, node):
        cfg = self.cloud.cloud_config.cloud
        runner = remote_runner.RemoteRunner(node, cfg.ssh_user,
                                            password=cfg.ssh_sudo_password)
        with settings(abort_on_prompts=True,
                      gateway=self.cloud.getIpSsh()):
            runner.run('echo')
