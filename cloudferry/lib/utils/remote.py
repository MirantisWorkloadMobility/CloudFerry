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
import os
import socket
import StringIO
import sys

import paramiko

from cloudferry.lib.utils import retrying

LOG = logging.getLogger(__name__)
SHELL = '/bin/bash -c'
WINDOW_SIZE = 2147483647  # https://github.com/paramiko/paramiko/issues/175


class RemoteFailure(Exception):
    """
    Remote execution failure
    """
    def __init__(self, message, output=None, full_command=None):
        super(RemoteFailure, self).__init__(message)
        self.output = output
        self.full_command = full_command


class RemoteExecutor(object):
    """
    Remote executor with minimal number of dependencies.
    """

    def __init__(self, cloud, hostname, ignore_errors=False):
        self.hostname = hostname
        self.ignore_errors = ignore_errors
        self.settings = cloud.ssh_settings
        self.connections = []
        self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        # TODO: connection_attempts
        settings = self.settings
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._retrying(client.connect,
                       hostname=self.hostname,
                       port=settings.port,
                       username=settings.username,
                       password=settings.password,
                       pkey=self._create_pkey(settings.private_key),
                       sock=self._connect_through_gateway(
                           self.hostname, settings.port, settings.gateway),
                       timeout=self.settings.timeout,
                       allow_agent=False,
                       look_for_keys=False,
                       compress=False)
        self.connections.append(client)
        self.client = client

    def close(self):
        self.client = None
        for connection in reversed(self.connections):
            connection.close()
        self.connections = []

    def sudo(self, cmd, **kwargs):
        formatted_cmd = cmd.format(**kwargs)
        if self.settings.username == 'root':
            return self._run(formatted_cmd, False)
        else:
            return self._run(formatted_cmd, True)

    def run(self, cmd, **kwargs):
        return self._run(cmd.format(**kwargs), False)

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

    @contextlib.contextmanager
    def open_file(self, filename, mode='r'):
        transport = self.client.get_transport()
        sftp_client = paramiko.SFTPClient.from_transport(
            transport, window_size=WINDOW_SIZE)
        with sftp_client:
            yield sftp_client.open(filename, mode, 512 * 1024 * 1024)

    def _connect_through_gateway(self, host, port, gateway):
        # TODO: connection_attempts
        if gateway is None:
            return None
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._retrying(client.connect,
                       hostname=gateway.hostname,
                       port=gateway.port,
                       username=gateway.username,
                       password=gateway.password,
                       pkey=self._create_pkey(gateway.private_key),
                       sock=self._connect_through_gateway(
                           gateway.hostname, gateway.port, gateway.gateway),
                       timeout=self.settings.timeout,
                       banner_timeout=self.settings.timeout,
                       allow_agent=False,
                       look_for_keys=False,
                       compress=False)
        self.connections.append(client)
        return self._retrying(
            client.get_transport().open_channel,
            'direct-tcpip', (host, port), ('', 0), window_size=WINDOW_SIZE)

    @staticmethod
    def _create_pkey(content):
        if content is None:
            return None
        saved_exceptions = []
        for key_cls in (paramiko.ECDSAKey, paramiko.RSAKey, paramiko.DSSKey):
            try:
                return key_cls.from_private_key(StringIO.StringIO(content))
            except paramiko.SSHException:
                saved_exceptions.append(sys.exc_info())

        for exc_info in saved_exceptions:
            LOG.error('Failed to decode SSH key', exc_info=exc_info)
        return None

    def _run(self, command, is_sudo):
        attempts = 0
        while True:
            try:
                LOG.debug('[%s] running command "%s"', self.hostname, command)
                if is_sudo:
                    sudo_prompt = '[{magic}] sudo password:'.format(
                        magic=os.urandom(8).encode('hex'))
                    prefix = 'sudo -p \\"{prompt}\\" '.format(
                        prompt=sudo_prompt)
                else:
                    sudo_prompt = None
                    prefix = ''
                full_command = 'LC_ALL=C {shell_cmd} "{prefix}{escaped_cmd}"'\
                    .format(shell_cmd=SHELL,
                            prefix=prefix,
                            escaped_cmd=self._shell_escape(command))

                session = self.client.get_transport().open_session(
                    window_size=WINDOW_SIZE)
                with session:
                    session.set_combine_stderr(True)
                    session.get_pty()
                    session.settimeout(self.settings.timeout)
                    session.exec_command(full_command)

                    output = ''
                    while not session.closed or session.recv_ready():
                        output += session.recv(1)
                        if sudo_prompt and output.endswith(sudo_prompt):
                            if self.settings.password is None:
                                raise RemoteFailure(
                                    'sudo require password, but no password '
                                    'provided in configuration.')
                            session.sendall(self.settings.password + '\n')
                            output = output[:-len(sudo_prompt)]

                    if not self.ignore_errors \
                            and session.recv_exit_status() != 0:
                        message = ('Error running command on host {host}: '
                                   '{cmd}').format(
                                       host=self.hostname, cmd=command)
                        LOG.debug('Error running command %s on host %s: %s',
                                  full_command, self.hostname, output)
                        raise RemoteFailure(message, output, full_command)

                return output
            except (paramiko.SSHException, socket.timeout):
                attempts += 1
                LOG.debug('Failed to execute command %s', command,
                          exc_info=True)
                if attempts >= self.settings.connection_attempts:
                    raise
                self._reconnect()

    @staticmethod
    def _shell_escape(str_value):
        for ch in ('$', '"', '`'):
            str_value = str_value.replace(ch, '\\' + ch)
        return str_value

    def _retrying(self, func, *args, **kwargs):
        retry = retrying.Retry(
            max_attempts=self.settings.connection_attempts,
            timeout=self.settings.attempt_failure_sleep,
            reraise_original_exception=True,
            expected_exceptions=(paramiko.BadHostKeyException,
                                 paramiko.AuthenticationException,
                                 RemoteFailure))
        return retry.run(func, *args, **kwargs)

    def _reconnect(self):
        self.close()
        self.connect()
