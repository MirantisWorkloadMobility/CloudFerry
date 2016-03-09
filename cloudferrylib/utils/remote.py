# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import contextlib
import logging

from fabric import api as fab_api
from fabric import state as fab_state
from fabric import network as fab_network

LOG = logging.getLogger(__name__)


class RemoteExecutor(object):
    """
    Remote executor with minimal number of dependencies.
    """

    def __init__(self, hostname, username, sudo_password=None, gateway=None,
                 connection_attempts=1, cipher=None, key_file=None,
                 ignore_errors=False):
        self.username = username
        self.sudo_password = sudo_password
        self.gateway = gateway
        self.connection_attempts = connection_attempts
        self.cipher = cipher
        self.key_file = key_file
        self.hostname = hostname
        self.ignore_errors = ignore_errors

    def sudo(self, cmd, **kwargs):
        formatted_cmd = cmd.format(**kwargs)
        if self.username != 'root':
            return self._run(fab_api.sudo, formatted_cmd)
        else:
            return self._run(fab_api.run, formatted_cmd)

    def run(self, cmd, **kwargs):
        return self._run(fab_api.run, cmd.format(**kwargs))

    def _run(self, run_function, command):
        # TODO: rewrite using plain paramiko for multithreading support
        LOG.debug('[%s] running command "%s"', self.hostname, command)
        abort_exception = None
        if self.ignore_errors:
            abort_exception = RuntimeError
        with fab_api.settings(
                fab_api.hide('warnings', 'running', 'stdout', 'stderr'),
                warn_only=self.ignore_errors,
                host_string=self.hostname,
                user=self.username,
                password=self.sudo_password,
                abort_exception=abort_exception,
                reject_unkown_hosts=False,
                combine_stderr=False,
                gateway=self.gateway,
                connection_attempts=self.connection_attempts):
            return run_function(command)

    def scp(self, src_path, host, dst_path, username=None, flags=None):
        command = 'scp -o StrictHostKeyChecking=no' \
                  ' -o UserKnownHostsFile=/dev/null'
        # Add flags
        if flags is not None:
            command += ' ' + flags

        # Add cipher option
        if self.cipher is not None:
            command += ' -c ' + self.cipher

        # Put source path
        command += ' \'{0}\''.format(src_path)

        # Put destination user/host
        if username is None:
            command += ' \'{0}\''.format(host)
        else:
            command += ' \'{0}\'@\'{1}\''.format(username, host)

        # Put destination path
        command += ':\'{0}\''.format(dst_path)

        # Execute
        return self.sudo(command)

    @contextlib.contextmanager
    def tmpdir(self, prefix='cloudferry'):
        path = None
        try:
            path = self.run(
                'mktemp -dt {prefix}_XXXXXX', prefix=prefix).strip()
            yield path
        finally:
            if path is not None:
                self.sudo('rm -rf {path}', path=path)

    @staticmethod
    def close_connection(hostname):
        for key, conn in fab_state.connections.items():
            _, conn_hostname = fab_network.normalize(key, True)
            if conn_hostname == hostname:
                conn.close()
                del fab_state.connections[key]
                break
