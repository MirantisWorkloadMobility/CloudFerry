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

import contextlib
import logging

from fabric import api
from oslo_config import cfg

from cloudferry.lib.base import exception
from cloudferry.lib.utils import retrying
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class RemoteExecutionError(exception.CFBaseException):
    pass


class RemoteTunnelOptions(object):
    def __init__(self, remote_port, port=None, host=None):
        """Options to create a tunnel forwarding a locally-visible port to
        the remote target.

        :param remote_port: the port on the remote host to listen to.
        :param port: the local or remote port to connect to. The default is
                     same port as a remote port.
        :param host: the locally-reachable host to connect to. The default is
                     ``localhost`` (the controller CF is running on).
        :param
        """
        self.remote_port = remote_port
        self.port = port
        self.host = host

    @contextlib.contextmanager
    def __call__(self):
        kwargs = {'remote_port': self.remote_port,
                  'local_port': self.port,
                  'local_host': self.host}
        # pylint: disable=not-context-manager
        with api.remote_tunnel(**{k: v for k, v in kwargs.items()
                                  if v is not None}):
            yield


class RemoteRunner(object):
    def __init__(self, host, user, password=None, sudo=False, key=None,
                 ignore_errors=False, timeout=None, gateway=None,
                 remote_tunnel=None):
        """ Runner a command on remote host.

        :param host: the remote host to execute a command.
        :param user: ssh user to connect to remote host.
        :param password: sudo password for remote host.
        :param sudo: execute a command as root.
        :param key: ssh key to connect to remote host.
        :param ignore_errors: ignore non-zero return codes.
        :param timeout: execute timeout
        :param gateway: ssh gateway to connect to the remote host
        :param remote_tunnel: the object of ``RemoteTunnelOptions`` class
        """
        self.host = host
        if key is None:
            key = CONF.migrate.key_filename
        self.user = user
        self.password = password
        self.sudo = sudo
        self.key = key
        self.ignore_errors = ignore_errors
        self.timeout = timeout
        self.gateway = gateway
        self.remote_tunnel = remote_tunnel

    def run(self, cmd, **kwargs):
        abort_exception = None
        if not self.ignore_errors:
            abort_exception = RemoteExecutionError

        if kwargs:
            cmd = cmd.format(**kwargs)

        ssh_attempts = CONF.migrate.ssh_connection_attempts

        if self.sudo and self.user != 'root':
            run = api.sudo
        else:
            run = api.run

        with api.settings(warn_only=self.ignore_errors,
                          host_string=self.host,
                          user=self.user,
                          password=self.password,
                          abort_exception=abort_exception,
                          reject_unkown_hosts=False,
                          combine_stderr=False,
                          connection_attempts=ssh_attempts,
                          command_timeout=self.timeout,
                          gateway=self.gateway):
            with utils.forward_agent(self.key):
                LOG.debug("running '%s' on '%s' host as user '%s'",
                          cmd, self.host, self.user)
                if self.remote_tunnel is not None:
                    with self.remote_tunnel():
                        result = run(cmd)
                else:
                    result = run(cmd)
                LOG.debug('[%s] Command "%s" result: %s',
                          self.host, cmd, result)
                return result

    def run_ignoring_errors(self, cmd, **kwargs):
        ignore_errors_original = self.ignore_errors
        try:
            self.ignore_errors = True
            return self.run(cmd, **kwargs)
        finally:
            self.ignore_errors = ignore_errors_original

    def run_repeat_on_errors(self, cmd, **kwargs):
        retrier = retrying.Retry(
            max_attempts=CONF.migrate.retry,
            reraise_original_exception=True,
            timeout=0,
        )
        return retrier.run(self.run, cmd, **kwargs)
