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
from cloudferrylib.copy_engines import bbcp_copier
from cloudferrylib.utils import local
from cloudferrylib.utils import remote_runner

from tests.cloudferrylib.copy_engines import test_base
from tests import test


class BbcpCopierTestCase(test_base.BaseTestCase):
    copier_class = bbcp_copier.BbcpCopier

    def setUp(self):
        super(BbcpCopierTestCase, self).setUp()
        self.src_cloud.hosts_with_bbcp = set()
        self.dst_cloud.hosts_with_bbcp = set()

    @mock.patch('os.path.isfile')
    def test_usage_false(self, mock_isfile):
        mock_isfile.return_value = False
        self.assertFalse(self.copier.check_usage(self.data))

        mock_isfile.return_value = True
        with mock.patch.object(self.copier, 'copy_bbcp',
                               side_effect=remote_runner.RemoteExecutionError):
            self.assertFalse(self.copier.check_usage(self.data))

    @mock.patch('os.path.isfile')
    def test_usage_true(self, mock_isfile):
        mock_isfile.return_value = True
        with mock.patch.object(self.copier, 'copy_bbcp') as mock_copy_bbcp:
            self.assertTrue(self.copier.check_usage(self.data))
            self.assertEqual(2, mock_copy_bbcp.call_count)

            mock_copy_bbcp.reset_mock()
            self.assertTrue(self.copier.check_usage(self.data))
            mock_copy_bbcp.assert_not_called()

    @mock.patch('cloudferrylib.utils.local.run')
    def test_transfer(self, mock_run):
        self.copier.transfer(self.data)
        self.assertCalledOnce(mock_run)

        mock_run.reset_mock()
        self.cfg.set_override('retry', 2, 'migrate')
        mock_run.side_effect = local.LocalExecutionFailed('fake', -1)
        with mock.patch.object(self.copier, 'clean_dst') as mock_clean_dst:
            self.assertRaises(base.FileCopyError, self.copier.transfer,
                              self.data)
            self.assertEqual(2, mock_run.call_count)
            self.assertCalledOnce(mock_clean_dst)

    @mock.patch('cloudferrylib.utils.local.run')
    def test_copy_bbcp(self, mock_run):
        with self.mock_runner() as runner:
            self.copier.copy_bbcp('fake_host', 'src')
            self.assertCalledOnce(runner.run)
            mock_run.assert_not_called()

            runner.reset_mock()
            runner.run.side_effect = (remote_runner.RemoteExecutionError, None)
            self.copier.copy_bbcp('fake_host', 'src')
            self.assertEqual(2, runner.run.call_count)
            self.assertCalledOnce(mock_run)


class RemoveBBCPTestCase(test.TestCase):
    @mock.patch('cloudferrylib.utils.remote_runner.RemoteRunner.'
                'run_ignoring_errors')
    def test_remove_bbcp(self, mock_run_ignoring_errors):
        cloud = mock.Mock()
        cloud.hosts_with_bbcp = {'fake_host_1', 'fake_host_2'}
        cloud.position = 'src'
        bbcp_copier.remove_bbcp(cloud)
        self.assertEqual(2, mock_run_ignoring_errors.call_count)
