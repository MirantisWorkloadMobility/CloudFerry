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
from cloudferrylib.copy_engines import rsync_copier
from cloudferrylib.utils import remote_runner

from tests.cloudferrylib.copy_engines import test_base


class RsyncCopierTestCase(test_base.BaseTestCase):
    copier_class = rsync_copier.RsyncCopier

    def test_check_usage(self):
        with self.mock_runner() as runner:
            runner.run.side_effect = (None, remote_runner.RemoteExecutionError)
            self.assertTrue(self.copier.check_usage(self.data))
            self.assertFalse(self.copier.check_usage(self.data))

    def test_transfer(self):
        with self.mock_runner() as runner:
            runner.run_repeat_on_errors.side_effect = (
                None,
                remote_runner.RemoteExecutionError)
            self.copier.transfer(self.data)
            self.assertCalledOnce(runner.run_repeat_on_errors)

            with mock.patch.object(self.copier, 'clean_dst') as mock_clean_dst:
                self.assertRaises(base.FileCopyError,
                                  self.copier.transfer, self.data)
                self.assertCalledOnce(mock_clean_dst)
