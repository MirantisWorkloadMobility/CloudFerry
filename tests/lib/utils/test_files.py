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

from cloudferry.lib.utils import files

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


class RemoteDFTestCase(test.TestCase):
    def test_gnu_df_parser(self):
        fs = '10.0.0.1:/nfs-dir/mount_point_A'
        num_blocks = 40317
        used = 2190
        available = 36079
        use_percent = 6
        mount_point = '/'

        df_output = (
            "Filesystem     1M-blocks  Used Available Use% Mounted on\n" +
            "{fs}          {mblocks}  {used}     {available}   " +
            "{use_percentage}% {mount_point}"
        ).format(fs=fs, mblocks=num_blocks, used=used, available=available,
                 use_percentage=use_percent, mount_point=mount_point)

        result = files.gnu_df_output_parser(df_output)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

        res = result[0]
        self.assertIsInstance(res, dict)
        self.assertEqual(res['filesystem'], fs)
        self.assertEqual(res['num_blocks'], num_blocks)
        self.assertEqual(res['blocks_used'], used)
        self.assertEqual(res['blocks_available'], available)
        self.assertEqual(res['use_percentage'], use_percent)
        self.assertEqual(res['mount_point'], mount_point)
