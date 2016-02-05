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
import logging
import math
import os

from fabric import api
from fabric import state

import cfglib


LOG = logging.getLogger(__name__)
CONF = cfglib.CONF


class RemoteSymlink(object):
    def __init__(self, runner, target, symlink_name):
        self.runner = runner
        self.target = target
        self.symlink = symlink_name

    def __enter__(self):
        if self.target is None:
            return

        cmd = "ln --symbolic {file} {symlink_name}".format(
            file=self.target, symlink_name=self.symlink)
        self.runner.run(cmd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.target is None:
            return

        self.runner.run_ignoring_errors(_unlink(self.symlink))
        return self


class RemoteTempFile(object):
    def __init__(self, runner, filename, text):
        self.runner = runner
        self.filename = os.path.join('/tmp', '{}'.format(filename))
        self.text = text

    def __enter__(self):
        cmd = "echo '{text}' > {file}".format(text=self.text,
                                              file=self.filename)
        self.runner.run(cmd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.runner.run_ignoring_errors(_unlink(self.filename))
        return self


class RemoteDir(object):
    def __init__(self, runner, dirname):
        self.runner = runner
        self.dirname = dirname

    def __enter__(self):
        cmd = "mkdir -p {dir}".format(dir=self.dirname)
        self.runner.run(cmd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.runner.run_ignoring_errors(_unlink_dir(self.dirname))


class GetTempDir(object):
    def __init__(self, runner, prefix):
        self.runner = runner
        self.prefix = prefix

    def get(self):
        cmd = "mktemp -udt %s_XXXX" % self.prefix
        return self.runner.run(cmd)


def _unlink(filename):
    return "rm -f {file}".format(file=filename)


def _unlink_dir(dirname):
    if len(dirname) > 1:
        return "rm -rf {dir}".format(dir=dirname)
    else:
        raise RuntimeError('Wrong dirname %s, stopping' % dirname)


class RemoteTempDir(object):
    """Creates remote temp dir using `mktemp` and removes it on scope exit"""

    def __init__(self, runner):
        self.runner = runner
        self.created_dir = None

    def __enter__(self):
        create_temp_dir = 'mktemp -d'
        self.created_dir = self.runner.run(create_temp_dir)
        if self.runner.sudo and self.runner.user != 'root':
            chown_created_dir_cmd = 'chown {user} {directory}'.format(
                user=self.runner.user, directory=self.created_dir)
            self.runner.run(chown_created_dir_cmd)
        return self.created_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        remove_dir = 'rm -rf {dir}'.format(dir=self.created_dir)
        self.runner.run_ignoring_errors(remove_dir)


def remote_file_size(runner, path):
    return int(runner.run('stat --printf="%s" {path}', path=path))


def remote_file_size_mb(runner, path):
    return int(math.ceil(remote_file_size(runner, path) / (1024.0 * 1024.0)))


class RemoteStdout(object):
    def __init__(self, host, user, cmd, **kwargs):
        self.host = host
        self.user = user
        if kwargs:
            cmd = cmd.format(**kwargs)
        self.cmd = cmd
        self.stdin = None
        self.stdout = None
        self.stderr = None

    def run(self):
        with api.settings(
                host_string=self.host,
                user=self.user,
                combine_stderr=False,
                connection_attempts=CONF.migrate.ssh_connection_attempts,
                reject_unkown_hosts=False,
        ):
            conn = state.connections[self.host]
            return conn.exec_command(self.cmd)

    def __enter__(self):
        self.stdin, self.stdout, self.stderr = self.run()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stdin:
            self.stdin.close()
        if self.stdout:
            self.stdout.close()
        if self.stderr:
            self.stderr.close()
        if all((exc_type, exc_val, exc_tb)):
            raise exc_type, exc_val, exc_tb
