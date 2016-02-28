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

from cloudferrylib.copy_engines import base
from cloudferrylib.copy_engines import scp_copier
from cloudferrylib.utils import sizeof_format

from tests.cloudferrylib.copy_engines import test_base


class SspCopierTestCase(test_base.BaseTestCase):
    copier_class = scp_copier.ScpCopier

    def test_run_scp(self):
        runner = mock.Mock()
        with mock.patch.object(
                self.copier, 'verify',
                side_effect=(False, True, False)) as mock_verify:
            self.cfg.set_override('retry', 2, 'migrate')
            self.copier.run_scp(runner, 'fake_src_path', 'fake_dst_host',
                                'fake_dst_path')
            self.assertEqual(2, runner.run.call_count)
            self.assertEqual(2, mock_verify.call_count)

            runner.reset_mock()
            mock_verify.reset_mock()
            self.cfg.set_override('retry', 1, 'migrate')
            self.assertRaises(base.FileCopyError, self.copier.run_scp, runner,
                              'fake_src_path', 'fake_dst_host',
                              'fake_dst_path')

    def test_transfer(self):
        with self.mock_runner() as runner:
            with mock.patch.object(self.copier, 'verify') as mock_verify:
                self.cfg.set_override('ssh_chunk_size', 10, 'migrate')
                runner.run.return_value = sizeof_format.parse_size('100M')
                with mock.patch.object(self.copier, 'run_scp') as mock_run_scp:
                    self.copier.transfer(self.data)
                    self.assertEqual(10, mock_run_scp.call_count)
                    self.assertCalledOnce(mock_verify)

    def test_verify_size(self):
        self.cfg.set_override('copy_with_md5_verification', False,
                              'migrate')
        with self.mock_runner() as runner:
            runner.run.side_effect = ('10', '20', '10', '10')
            self.data['path_src'] = 'fake_path_src_1'
            self.data['path_dst'] = 'fake_path_dst_1'
            self.assertFalse(self.copier.verify(self.data))

            self.data['path_src'] = 'fake_path_src_2'
            self.data['path_dst'] = 'fake_path_dst_2'
            self.assertTrue(self.copier.verify(self.data))

    def test_verify_md5(self):
        self.cfg.set_override('copy_with_md5_verification', True,
                              'migrate')
        with self.mock_runner() as runner:
            runner.run.side_effect = ('10', '10', 'md5_1', 'md5_2')
            self.data['path_src'] = 'fake_path_src_1'
            self.data['path_dst'] = 'fake_path_dst_1'
            self.assertFalse(self.copier.verify(self.data))

            self.data['path_src'] = 'fake_path_src_2'
            self.data['path_dst'] = 'fake_path_dst_2'
            runner.run.side_effect = ('10', '10', 'md5_1', 'md5_1')
            self.assertTrue(self.copier.verify(self.data))
