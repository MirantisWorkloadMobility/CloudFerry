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
from cloudferrylib.utils.drivers import ssh_chunks

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


class SplitterTestCase(test.TestCase):
    def test_makes_one_iteration_if_total_is_zero(self):
        total = 0
        block = 10

        for start, end in ssh_chunks.splitter(total, block):
            self.assertEqual(start, 0)
            self.assertEqual(end, 0)

    def test_one_chunk_for_one_mb_total(self):
        total = 1
        block = 10

        for start, end in ssh_chunks.splitter(total, block):
            self.assertEqual(start, 0)
            self.assertEqual(end, total)

    def test_keeps_correct_number_of_iterations_for_uneven_totals(self):
        total = 101
        block = 10

        expected_iterations = total / block
        if total % block != 0:
            expected_iterations += 1

        actual_iterations = 0
        for _, _ in ssh_chunks.splitter(total, block):
            actual_iterations += 1

        self.assertEqual(actual_iterations, expected_iterations)


class VerifiedFileCopyTestCase(test.TestCase):
    @mock.patch("tests.cloudferrylib.utils.test_file_utils.ssh_chunks."
                "remote_scp")
    @mock.patch("tests.cloudferrylib.utils.test_file_utils.ssh_chunks."
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

        self.assertRaises(ssh_chunks.FileCopyFailure,
                          ssh_chunks.verified_file_copy, src_runner,
                          dst_runner, user, src_path, dst_path, dest_host,
                          num_retries)

    @mock.patch("tests.cloudferrylib.utils.test_file_utils.ssh_chunks."
                "remote_scp")
    @mock.patch("tests.cloudferrylib.utils.test_file_utils.ssh_chunks."
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
            ssh_chunks.verified_file_copy(src_runner, dst_runner, user,
                                          src_path, dst_path, dest_host,
                                          num_retries)
        except ssh_chunks.FileCopyFailure:
            assert scp.call_count == num_retries + 1
