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
import os

from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class RemoteSymlink(object):
    def __init__(self, runner, target, symlink_name):
        self.runner = runner
        self.target = target
        self.symlink = symlink_name

    def __enter__(self):
        cmd = "ln --symbolic {file} {symlink_name}".format(
            file=self.target, symlink_name=self.symlink)
        self.runner.run(cmd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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
        if dirname == '/':
            raise ValueError("The directory / is not allowed")
        else:
            self.dirname = dirname

    def __enter__(self):
        cmd = "mkdir -p {dir}".format(dir=self.dirname)
        self.runner.run(cmd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.runner.run_ignoring_errors(_unlink_dir(self.dirname))
        return self


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

    def __enter__(self):
        create_temp_dir = 'mktemp -d'
        self.created_dir = self.runner.run(create_temp_dir)
        return self.created_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        remove_dir = 'rm -rf {dir}'.format(dir=self.created_dir)
        self.runner.run_ignoring_errors(remove_dir)
