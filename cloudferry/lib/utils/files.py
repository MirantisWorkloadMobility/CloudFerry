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
import re
import os

from fabric import api
from fabric import state

from cloudferry import cfglib
from cloudferry.lib.utils import remote_runner

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


class FullAccessRemoteDir(RemoteDir):
    def __init__(self, runner, dirname):
        super(FullAccessRemoteDir, self).__init__(runner, dirname)
        self.old_perms = None

    def __enter__(self):
        new_dir = super(FullAccessRemoteDir, self).__enter__()
        self.old_perms = try_remote_get_file_permissions(self.runner,
                                                         self.dirname)
        try_remote_chmod(self.runner, 777, self.dirname)
        return new_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        super(FullAccessRemoteDir, self).__exit__(exc_type, exc_val, exc_tb)
        if self.old_perms:
            try_remote_chmod(self.runner, self.old_perms, self.dirname)


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


class grant_all_permissions(object):
    def __init__(self, runner, path):
        self.runner = runner
        self.file_path = path
        self.dir_path = os.path.dirname(path)
        self.old_file_perms = None
        self.old_dir_perms = None

    def __enter__(self):
        self.grant_permissions()

    def __exit__(self, *_):
        self.restore_permissions()

    def grant_permissions(self):
        self.old_dir_perms = remote_get_file_permissions(self.runner,
                                                         self.dir_path)
        # there may be no file in destination (which is fine)
        self.old_file_perms = try_remote_get_file_permissions(self.runner,
                                                              self.file_path)
        LOG.debug("Temporarily adding full access to '%s' dir on '%s' host",
                  self.dir_path, self.runner.host)
        try_remote_chmod(self.runner, 777, self.dir_path)
        LOG.debug("Temporarily adding full access to '%s' file on '%s' host",
                  self.file_path, self.runner.host)
        try_remote_chmod(self.runner, 666, self.file_path)

    def _restore_access(self, path, perms):
        if perms:
            LOG.debug("Restoring access mode '%s' for '%s' file on '%s' host",
                      perms, path, self.runner.host)
            try_remote_chmod(self.runner, perms, path)

    def restore_permissions(self):
        self._restore_access(self.file_path, self.old_file_perms)
        self._restore_access(self.dir_path, self.old_dir_perms)


BLOCKSIZE_K = 1 << 10
BLOCKSIZE_M = BLOCKSIZE_K << 10
BLOCKSIZE_G = BLOCKSIZE_M << 10


def gnu_df_output_parser(df_output):
    path_pattern = r'[\w/.:-]+'

    pattern = r'^({path_pattern})\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%\s+' \
              r'({path_pattern})$'.format(path_pattern=path_pattern)

    res = []

    # ignore header
    for line in df_output.splitlines()[1:]:
        matched = re.match(pattern, line)

        if matched is None:
            LOG.debug("Unexpected output from 'df', failed to parse line "
                      "'%s'!", line)
            continue

        fs, nblocks, used, avail, percentage, mount = matched.groups()
        res.append({
            'filesystem': fs,
            'num_blocks': int(nblocks),
            'blocks_used': int(used),
            'blocks_available': int(avail),
            'use_percentage': int(percentage),
            'mount_point': mount
        })

    return res


def remote_df(runner, path=None, block_size=BLOCKSIZE_M):
    if path is None:
        path = ''

    df_cmd = 'BLOCKSIZE={block_size} df --portability {path}'.format(
        block_size=block_size, path=path)
    df_output = runner.run(df_cmd)

    return gnu_df_output_parser(df_output)


def remote_free_space(runner, path, block_size=BLOCKSIZE_M):
    try:
        # there should be only one mount point for a path
        df_result = remote_df(runner, path, block_size=block_size)[0]
        return df_result['blocks_available']
    except (IndexError, KeyError) as e:
        LOG.debug("Failed to get free space for path '%s' on node '%s': %s",
                  path, runner.host, e)
        return 0


def remote_file_size(runner, path):
    return int(runner.run('stat --printf="%s" {path}', path=path))


def remote_file_size_mb(runner, path):
    return int(math.ceil(remote_file_size(runner, path) / (1024.0 * 1024.0)))


def remote_get_file_permissions(runner, path):
    """Returns file/dir permissions in octal format"""
    return str(runner.run('stat -c \'%a\' "{path}"', path=path))


def remote_chmod(runner, octal_perms, path):
    runner.run('chmod {perms} "{path}"'.format(path=path, perms=octal_perms))


def try_remote_chmod(runner, octal_perms, path):
    try:
        remote_chmod(runner, octal_perms, path)
    except remote_runner.RemoteExecutionError as e:
        LOG.debug("chmod '%s' '%s' on node %s failed with: %s", octal_perms,
                  path, runner.host, e)


def try_remote_get_file_permissions(runner, path):
    """Returns file/dir permissions in octal format, or `None` in case of
    error"""
    try:
        return remote_get_file_permissions(runner, path)
    except remote_runner.RemoteExecutionError as e:
        LOG.debug("Can't get file permissions for path '%s' on host '%s': %s",
                  path, runner.host, e)


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
