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
import mock
from cloudferrylib.utils import files
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils.drivers import copy_engine
from tests import test


class RemoteSymlinkTestCase(test.TestCase):
    def test_symlink_is_removed_on_scope_exit(self):
        runner = mock.Mock()
        target = "/tmp/filename"
        symlink = "_symlink"

        with files.RemoteSymlink(runner, target, symlink):
            pass

        create_symlink = "ln --symbolic %s %s" % (target, symlink)
        rm_symlink = "rm -f %s" % symlink

        runner.run.assert_called_once_with(create_symlink)
        runner.run_ignoring_errors.assert_called_once_with(rm_symlink)

    def test_symlink_does_nothing_if_target_file_is_none(self):
        runner = mock.Mock()
        target = None
        symlink = "_symlink"

        with files.RemoteSymlink(runner, target, symlink):
            pass

        assert not runner.run.called
        assert not runner.run_ignoring_errors.called


class RemoteTempFileTestCase(test.TestCase):
    def test_temp_file_is_deleted_on_scope_exit(self):
        runner = mock.Mock()
        filename = 'file'
        contents = 'contents'

        with files.RemoteTempFile(runner, filename, contents):
            pass

        rm_file = "rm -f /tmp/{}".format(filename)
        runner.run_ignoring_errors.assert_called_once_with(rm_file)


class RemoteDirTestCase(test.TestCase):
    def test_temp_dir_is_deleted_on_scope_exit(self):
        runner = mock.Mock()
        dirname = 'dir'

        with files.RemoteDir(runner, dirname):
            pass

        rm_dir = "rm -rf {}".format(dirname)
        runner.run_ignoring_errors.assert_called_once_with(rm_dir)


class VerifiedFileCopyTestCase(test.TestCase):
    @mock.patch("tests.cloudferrylib.utils.test_file_utils.copy_engine."
                "remote_scp")
    @mock.patch("tests.cloudferrylib.utils.test_file_utils.copy_engine."
                "remote_md5_sum")
    def test_raises_error_on_copy_failure(self, scp, _):
        src_runner = mock.Mock()
        dst_runner = mock.Mock()

        user = 'dstuser'
        src_path = '/tmp/srcfile'
        dst_path = '/tmp/dstfile'
        dest_host = 'desthostname'
        num_retries = 1

        scp.side_effect = remote_runner.RemoteExecutionError

        self.assertRaises(copy_engine.FileCopyFailure,
                          copy_engine.verified_file_copy, src_runner,
                          dst_runner, user, src_path, dst_path, dest_host,
                          num_retries)

    @mock.patch("tests.cloudferrylib.utils.test_file_utils.copy_engine."
                "remote_scp")
    @mock.patch("tests.cloudferrylib.utils.test_file_utils.copy_engine."
                "remote_md5_sum")
    def test_retries_if_error_occurs(self, scp, _):
        src_runner = mock.Mock()
        dst_runner = mock.Mock()

        user = 'dstuser'
        src_path = '/tmp/srcfile'
        dst_path = '/tmp/dstfile'
        dest_host = 'desthostname'
        num_retries = 10

        scp.side_effect = remote_runner.RemoteExecutionError

        try:
            copy_engine.verified_file_copy(src_runner, dst_runner, user,
                                           src_path, dst_path, dest_host,
                                           num_retries)
        except copy_engine.FileCopyFailure:
            assert scp.call_count == num_retries + 1

    def test_temp_dir_exception_inside_with(self):
        runner = mock.Mock()
        dirname = 'dir'

        res = False
        try:
            with files.RemoteDir(runner, dirname):
                raise Exception
        except Exception:
            res = True
        self.assertTrue(res)
