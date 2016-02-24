# Copyright (c) 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

import mock

from cloudferrylib.utils import files

from tests import test


class RemoteSymlinkTestCase(test.TestCase):
    def test_symlink_is_removed_on_scope_exit(self):
        runner = mock.Mock()
        target = "/tmp/filename"
        symlink = "_symlink"

        with files.RemoteSymlink(runner, target, symlink):
            pass

        self.assertCalledOnce(runner.run)
        self.assertCalledOnce(runner.run_ignoring_errors)

    def test_symlink_does_nothing_if_target_file_is_none(self):
        runner = mock.Mock()
        target = None
        symlink = "_symlink"

        with files.RemoteSymlink(runner, target, symlink):
            pass

        runner.run.assert_not_called()
        runner.run_ignoring_errors.assert_not_called()


class RemoteTempFileTestCase(test.TestCase):
    def test_temp_file_is_deleted_on_scope_exit(self):
        runner = mock.Mock()
        filename = 'file'
        contents = 'contents'

        with files.RemoteTempFile(runner, filename, contents):
            pass

        self.assertCalledOnce(runner.run_ignoring_errors)


class RemoteDirTestCase(test.TestCase):
    def test_temp_dir_is_deleted_on_scope_exit(self):
        runner = mock.Mock()
        dirname = 'dir'

        with files.RemoteDir(runner, dirname):
            pass

        self.assertCalledOnce(runner.run_ignoring_errors)
