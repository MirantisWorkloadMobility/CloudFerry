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
import atexit
import contextlib
import logging
import os
import re
import signal
import socket
import StringIO
import subprocess
import tempfile

import paramiko
import paramiko.agent
import paramiko.util

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
        if not isinstance(hostname, basestring):
            hostname = _get_ip_from_node(cloud, hostname)

        assert hostname is not None

        self.cloud_name = cloud.name
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
        settings = self.settings
        LOG.debug('Connecting to %s@%s:%s [cloud: %s]',
                  settings.username, self.hostname, settings.port,
                  self.cloud_name)
        gateway_socket = self._connect_through_gateway(
            self.hostname, settings.port, settings.gateway)
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._retrying(client.connect,
                           hostname=self.hostname,
                           port=settings.port,
                           username=settings.username,
                           password=settings.password,
                           pkey=create_pkey(settings.private_key),
                           sock=gateway_socket,
                           timeout=self.settings.timeout,
                           allow_agent=False,
                           look_for_keys=False,
                           compress=False)
            self.connections.append(client)
            self.client = client
        except paramiko.SSHException as ex:
            LOG.error('Failed to connect to host \'%s\' in cloud \'%s\' '
                      'through SSH: %s', self.hostname, self.cloud_name, ex)
            raise

    def close(self):
        self.client = None
        for connection in reversed(self.connections):
            connection.close()
        self.connections = []

    def sudo(self, cmd, agent=None, **kwargs):
        formatted_cmd = cmd.format(**kwargs)
        if self.settings.username == 'root':
            return self._run(formatted_cmd, False, agent)
        else:
            return self._run(formatted_cmd, True, agent)

    def run(self, cmd, agent=None, **kwargs):
        return self._run(cmd.format(**kwargs), False, agent)

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
        if gateway is None:
            return None
        LOG.debug('Connecting to %s@%s:%s [cloud: %s]',
                  gateway.username, gateway.hostname, gateway.port,
                  self.cloud_name)
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._retrying(client.connect,
                           hostname=gateway.hostname,
                           port=gateway.port,
                           username=gateway.username,
                           password=gateway.password,
                           pkey=create_pkey(gateway.private_key),
                           sock=self._connect_through_gateway(
                               gateway.hostname, gateway.port,
                               gateway.gateway),
                           timeout=self.settings.timeout,
                           banner_timeout=self.settings.timeout,
                           allow_agent=False,
                           look_for_keys=False,
                           compress=False)
            self.connections.append(client)
            return self._retrying(
                client.get_transport().open_channel,
                'direct-tcpip', (host, port), ('', 0), window_size=WINDOW_SIZE)
        except paramiko.SSHException as ex:
            LOG.error('Failed to connect to SSH gateway \'%s\' for cloud '
                      '\'%s\': %s', gateway.hostname, self.cloud_name, ex)
            raise

    def _run(self, command, is_sudo, agent):
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
                if agent and agent.auth_sock:
                    AgentRequestHandler(session, agent.auth_sock)
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


def _get_ip_from_node(cloud, compute_node):
    candidates = []
    if cloud.access_iface:
        candidates = list(_strip_suffix(
            compute_node.interfaces.get(cloud.access_iface, [])))
    else:
        for addresses in compute_node.interfaces.values():
            candidates.extend(_strip_suffix(addresses))

    if cloud.access_networks:
        candidates = [addr for addr in candidates
                      if any(addr in net for net in cloud.access_networks)]

    if len(candidates) != 1:
        raise RemoteFailure(
            '{n} IP address found for compute node "{host}": {addrs}'.format(
                n=len(candidates), host=compute_node.object_id.id,
                addrs=', '.join(candidates)))
    return candidates[0]


def _strip_suffix(addresses):
    for address in addresses:
        if '/' in address:
            address, _ = address.split('/')
        yield address


def create_pkey(content):
    if content is None:
        return None
    for key_cls in (paramiko.ECDSAKey, paramiko.RSAKey, paramiko.DSSKey):
        try:
            return key_cls.from_private_key(StringIO.StringIO(content))
        except paramiko.SSHException:
            pass

    LOG.error('Failed to decode SSH key')
    return None


class SSHAgent(object):
    def __init__(self):
        self.agent_pid = None
        self.auth_sock = None

    def start(self):
        assert self.auth_sock is None and self.agent_pid is None
        process = subprocess.Popen(['ssh-agent', '-s'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, _ = process.communicate()
        auth_sock_re = re.compile(r'^SSH_AUTH_SOCK=([^;]+);.*$')
        agent_pid_re = re.compile(r'^SSH_AGENT_PID=([0-9]+);.*$')

        auth_sock, agent_pid = None, None
        for line in stdout.splitlines():
            if not auth_sock:
                match = auth_sock_re.match(line)
                if match is not None:
                    auth_sock = match.group(1)
            if not agent_pid:
                match = agent_pid_re.match(line)
                if match is not None:
                    agent_pid = int(match.group(1))

        if agent_pid:
            self.auth_sock = auth_sock
            self.agent_pid = agent_pid
            atexit.register(self.terminate)

        if not agent_pid or not auth_sock:
            LOG.error('Failed to parse ssh-agent output: %s', repr(stdout))
            raise RuntimeError('Failed to parse ssh-agent output')

    def terminate(self):
        if self.agent_pid is not None:
            os.kill(self.agent_pid, signal.SIGTERM)
            self.agent_pid = None
            self.auth_sock = None

    def add_key(self, key):
        assert self.auth_sock is not None and self.agent_pid is not None

        key = create_pkey(key)
        if key is None:
            return

        with tempfile.NamedTemporaryFile() as ntf:
            key.write_private_key(ntf.file)
            ntf.file.flush()
            process = subprocess.Popen(
                ['ssh-add', ntf.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={
                    'SSH_AUTH_SOCK': self.auth_sock,
                    'SSH_AGENT_PID': str(self.agent_pid),
                })

            stdout, _ = process.communicate()
            if process.returncode:
                LOG.error('Failed to add key to SSH agent: %s', stdout)


class AgentClientProxy(paramiko.agent.AgentClientProxy):
    def __init__(self, chan_remote, auth_sock):
        self.auth_sock = auth_sock
        super(AgentClientProxy, self).__init__(chan_remote)

    def connect(self):
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        paramiko.util.retry_on_signal(lambda: conn.connect(self.auth_sock))
        self._conn = conn


class AgentRequestHandler(paramiko.agent.AgentRequestHandler):
    def __init__(self, chan_client, auth_sock):
        self.auth_sock = auth_sock
        super(AgentRequestHandler, self).__init__(chan_client)

    def _forward_agent_handler(self, chan_remote):
        self.__clientProxys.append(
            AgentClientProxy(chan_remote, self.auth_sock))
