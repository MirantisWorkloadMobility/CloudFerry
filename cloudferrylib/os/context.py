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

from cloudferrylib.os import clients
from cloudferrylib.utils import utils

LOG = logging.getLogger(__name__)
MODEL_LIST = [
    'cloudferrylib.os.discovery.keystone.Tenant',
    'cloudferrylib.os.discovery.glance.Image',
    'cloudferrylib.os.discovery.cinder.Volume',
    'cloudferrylib.os.discovery.nova.Server',
]


class SshSettings(object):
    def __init__(self, username, sudo_password=None, gateway=None,
                 connection_attempts=1, cipher=None, key_file=None):
        self.username = username
        self.sudo_password = sudo_password
        self.gateway = gateway
        self.connection_attempts = connection_attempts
        self.cipher = cipher
        self.key_file = key_file


class Context(object):
    def __init__(self, clouds=None):
        self.clouds = {}
        for name, cloud in (clouds or {}).items():
            credential = clients.Credential(**cloud['credential'])
            scope = clients.Scope(**cloud['scope'])
            ssh_settings = SshSettings(**cloud['ssh'])
            self.clouds[name] = OpenstackCloud(name, credential, scope,
                                               ssh_settings)

    def get_cloud(self, name):
        return self.clouds[name]


class RemoteExecutor(object):
    def __init__(self, ssh_settings, hostname, ignore_errors):
        self.ssh_settings = ssh_settings
        self.hostname = hostname
        self.ignore_errors = ignore_errors

    def sudo(self, cmd, **kwargs):
        formatted_cmd = cmd.format(**kwargs)
        if self.ssh_settings.username != 'root':
            return self._run(fab_api.sudo, formatted_cmd)
        else:
            return self._run(fab_api.run, formatted_cmd)

    def run(self, cmd, **kwargs):
        return self._run(fab_api.run, cmd.format(**kwargs))

    def _run(self, run_function, command):
        LOG.debug('[%s] running command "%s"', self.hostname, command)
        abort_exception = None
        if self.ignore_errors:
            abort_exception = RuntimeError
        with fab_api.settings(
                fab_api.hide('warnings', 'running', 'stdout', 'stderr'),
                warn_only=self.ignore_errors,
                host_string=self.hostname,
                user=self.ssh_settings.username,
                password=self.ssh_settings.sudo_password,
                abort_exception=abort_exception,
                reject_unkown_hosts=False,
                combine_stderr=False,
                gateway=self.ssh_settings.gateway,
                connection_attempts=self.ssh_settings.connection_attempts):
            return run_function(command)

    def scp(self, src_path, host, dst_path, username=None, flags=None):
        command = 'scp -o StrictHostKeyChecking=no' \
                  ' -o UserKnownHostsFile=/dev/null'
        # Add flags
        if flags is not None:
            command += ' ' + flags

        # Add cipher option
        if self.ssh_settings.cipher is not None:
            command += ' -c ' + self.ssh_settings.cipher

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


class OpenstackCloud(object):
    def __init__(self, name, credential, scope, ssh_settings, discover=None):
        if discover is None:
            discover = MODEL_LIST
        self.name = name
        self.credential = credential
        self.scope = scope
        self.ssh_settings = ssh_settings
        self.discover = discover

    def image_client(self, scope=None):
        return clients.image_client(self.credential, scope or self.scope)

    def identity_client(self, scope=None):
        return clients.identity_client(self.credential, scope or self.scope)

    def volume_client(self, scope=None):
        return clients.volume_client(self.credential, scope or self.scope)

    def compute_client(self, scope=None):
        return clients.compute_client(self.credential, scope or self.scope)

    @contextlib.contextmanager
    def remote_executor(self, hostname, key_file=None, ignore_errors=False):
        key_files = []
        if self.ssh_settings.key_file is not None:
            key_files.append(self.ssh_settings.key_file)
        if key_file is not None:
            key_files.append(key_file)
        if key_files:
            utils.ensure_ssh_key_added(key_files)
        try:
            yield RemoteExecutor(self.ssh_settings, hostname, ignore_errors)
        finally:
            _close_connection(hostname)


def _close_connection(hostname):
    for key, conn in fab_state.connections.items():
        _, conn_hostname = fab_network.normalize(key, True)
        if conn_hostname == hostname:
            conn.close()
            del fab_state.connections[key]
            break
