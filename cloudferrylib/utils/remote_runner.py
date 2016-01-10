# Copyright 2015 Mirantis Inc.
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

from fabric.api import sudo as fab_sudo
from fabric.api import run
from fabric.api import settings

import cfglib
from cloudferrylib.utils import log
from cloudferrylib.utils.utils import forward_agent

LOG = log.getLogger(__name__)


class RemoteExecutionError(RuntimeError):
    pass


class RemoteRunner(object):
    def __init__(self, host, user, password=None, sudo=False, key=None,
                 ignore_errors=False):
        self.host = host
        if key is None:
            key = cfglib.CONF.migrate.key_filename
        self.user = user
        self.password = password
        self.sudo = sudo
        self.key = key
        self.ignore_errors = ignore_errors

    def run(self, cmd, **kwargs):
        abort_exception = None
        if not self.ignore_errors:
            abort_exception = RemoteExecutionError

        if kwargs:
            cmd = cmd.format(**kwargs)

        ssh_attempts = cfglib.CONF.migrate.ssh_connection_attempts

        with settings(warn_only=self.ignore_errors,
                      host_string=self.host,
                      user=self.user,
                      password=self.password,
                      abort_exception=abort_exception,
                      reject_unkown_hosts=False,
                      combine_stderr=False,
                      connection_attempts=ssh_attempts):
            with forward_agent(self.key):
                LOG.debug("running '%s' on '%s' host as user '%s'",
                          cmd, self.host, self.user)
                if self.sudo and self.user != 'root':
                    return fab_sudo(cmd)
                else:
                    return run(cmd)

    def run_ignoring_errors(self, cmd, **kwargs):
        ignore_errors_original = self.ignore_errors
        try:
            self.ignore_errors = True
            self.run(cmd, **kwargs)
        finally:
            self.ignore_errors = ignore_errors_original

    def run_repeat_on_errors(self, cmd):
        done = False
        attempts = 0

        while not done:
            try:
                attempts += 1
                self.run(cmd)
                done = True
            except RemoteExecutionError as e:
                if attempts >= cfglib.CONF.migrate.ssh_connection_attempts:
                    raise e
