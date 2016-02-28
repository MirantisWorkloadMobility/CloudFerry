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

from cloudferrylib.utils import remote_runner


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

        cmd = "ln --symbolic {file} {symlink_name}"
        self.runner.run(cmd, file=self.target, symlink_name=self.symlink)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.target is None:
            return
        remote_rm(self.runner, self.symlink, ignoring_errors=True)
        return self


class RemoteTempFile(object):
    def __init__(self, runner, filename, text):
        self.runner = runner
        self.filename = os.path.join('/tmp', filename)
        self.text = text

    def __enter__(self):
        cmd = "echo '{text}' > {filename}"
        self.runner.run(cmd, text=self.text, filename=self.filename)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        remote_rm(self.runner, self.filename, ignoring_errors=True)
        return self


class RemoteDir(object):
    def __init__(self, runner, dirname):
        self.runner = runner
        self.dirname = dirname

    def __enter__(self):
        cmd = "mkdir -p {dir}"
        self.runner.run(cmd, dir=self.dirname)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        remote_rm(self.runner, self.dirname, recursive=True,
                  ignoring_errors=True)


def is_installed(runner, cmd):
    try:
        is_installed_cmd = "type {cmd} >/dev/null 2>&1".format(cmd=cmd)
        runner.run(is_installed_cmd)
        return True
    except remote_runner.RemoteExecutionError:
        return False


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


def remote_file_size(runner, path):
    return int(runner.run('stat --printf="%s" {path}', path=path))


def remote_file_size_mb(runner, path):
    return int(math.ceil(remote_file_size(runner, path) / (1024.0 * 1024.0)))


def remote_md5_sum(runner, path):
    get_md5 = "md5sum {path} | awk '{{ print $1 }}'"
    return runner.run(get_md5, path=path)


def remote_rm(runner, path, recursive=False, ignoring_errors=False):
    options = 'f'
    if recursive:
        options += 'r'
    cmd = "rm -{options} {path}"
    run = runner.run_ignoring_errors if ignoring_errors else runner.run
    run(cmd, options=options, path=path)


def remote_gzip(runner, path):
    cmd = "gzip -f {path}"
    runner.run(cmd, path=path)
    return path + ".gz"


def remote_split_file(runner, input, output, start, block_size):
    cmd = ("dd if={input} of={output} skip={start} bs={block_size}M "
           "count=1")
    runner.run(cmd, input=input, output=output, block_size=block_size,
               start=start)


def remote_unzip(runner, path):
    cmd = "gzip -f -d {path}"
    runner.run(cmd, path=path)


def remote_join_file(runner, dest_file, part, start, block_size):
    cmd = ("dd if={part} of={dest} seek={start} bs={block_size}M "
           "count=1")
    runner.run(cmd, part=part, dest=dest_file, start=start,
               block_size=block_size)
