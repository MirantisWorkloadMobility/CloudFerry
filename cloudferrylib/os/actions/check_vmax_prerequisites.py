# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from cloudferrylib.base import exception
from cloudferrylib.base.action import action
from cloudferrylib.utils import local
from cloudferrylib.utils import remote_runner

LOG = logging.getLogger(__name__)


class CheckVMAXPrerequisites(action.Action):
    """This verifies prerequisites required for NFS to VMAX iSCSI cinder
    volume migration"""

    def _iscsiadm_is_installed_locally(self):
        LOG.info("Checking if iscsiadm tool is installed")
        try:
            local.run('iscsiadm --help &>/dev/null')
        except local.LocalExecutionFailed:
            msg = ("iscsiadm is not available on the local host. Please "
                   "install iscsiadm tool on the node you running on or "
                   "choose other cinder backend for migration. iscsiadm is "
                   "mandatory for migrations with EMC VMAX cinder backend")
            LOG.error(msg)
            raise exception.AbortMigrationError(msg)

    def _ssh_connectivity_between_controllers(self):
        src_host = self.cfg.src.ssh_host
        src_user = self.cfg.src.ssh_user
        dst_host = self.cfg.dst.ssh_host
        dst_user = self.cfg.dst.ssh_user

        LOG.info("Checking ssh connectivity between '%s' and '%s'",
                 src_host, dst_host)

        rr = remote_runner.RemoteRunner(src_host, src_user)

        ssh_opts = ('-o UserKnownHostsFile=/dev/null '
                    '-o StrictHostKeyChecking=no')

        cmd = "ssh {opts} {user}@{host} 'echo ok'".format(opts=ssh_opts,
                                                          user=dst_user,
                                                          host=dst_host)

        try:
            rr.run(cmd)
        except remote_runner.RemoteExecutionError:
            msg = ("No ssh connectivity between source host '{src_host}' and "
                   "destination host '{dst_host}'. Make sure you have keys "
                   "and correct configuration on these nodes. To verify run "
                   "'{ssh_cmd}' from '{src_host}' node")
            msg = msg.format(src_host=src_host, dst_host=dst_host, ssh_cmd=cmd)
            LOG.error(msg)
            raise exception.AbortMigrationError(msg)

    def run(self, **kwargs):
        if self.cfg.dst_storage.backend != 'iscsi-vmax':
            return
        self._iscsiadm_is_installed_locally()
        self._ssh_connectivity_between_controllers()
