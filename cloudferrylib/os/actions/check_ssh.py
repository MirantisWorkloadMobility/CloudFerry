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
from operator import itemgetter

from fabric.api import settings

from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import log
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)


class CheckSSH(action.Action):
    def run(self, info=None, **kwargs):
        check_results = []
        check_failed = False

        for node in self.get_compute_nodes():
            node_ssh_failed = self.check_access(node)
            check_failed = check_failed or node_ssh_failed
            check_results.append((node, node_ssh_failed))

        if check_failed:
            message = "SSH check failed for following nodes: '{nodes}'".format(
                nodes=map(itemgetter(0),
                          filter(lambda (n, status): status, check_results)))
            LOG.error(message)
            raise exception.AbortMigrationError(message)

    def get_compute_nodes(self):
        return self.cloud.resources[utils.COMPUTE_RESOURCE].get_compute_hosts()

    def check_access(self, node):
        ssh_access_failed = False

        cfg = self.cloud.cloud_config.cloud
        runner = remote_runner.RemoteRunner(node, cfg.ssh_user,
                                            password=cfg.ssh_sudo_password)
        gateway = self.cloud.getIpSsh()
        ssh_attempts = self.cloud.cloud_config.migrate.ssh_connection_attempts

        try:
            with settings(gateway=gateway, connection_attempts=ssh_attempts):
                runner.run('echo')
        except Exception as error:
            LOG.error("SSH connection from '%s' to '%s' failed with error: "
                      "'%s'", gateway, node, error.message)
            ssh_access_failed = True

        return ssh_access_failed
