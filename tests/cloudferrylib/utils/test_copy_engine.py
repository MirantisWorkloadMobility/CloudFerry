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

import inspect
import mock

from cloudferrylib.utils.remote_runner import RemoteExecutionError
from cloudferrylib.utils.drivers import copy_engine

from tests import test


class CopyFileTestCase(test.TestCase):
    @mock.patch("cloudferrylib.utils.drivers.copy_engine.remote_runner."
                "RemoteRunner.run")
    def test_uses_rsync_if_its_available(self, rr):
        host = 'host'
        user = 'user'
        password = 'password'
        config = mock.Mock()
        config.migrate.ephemeral_copy_backend = 'rsync'

        rr.return_value = None

        engine = copy_engine.file_transfer_engine(config, host, user, password)

        self.assertTrue(inspect.isclass(engine))

        src_cloud = mock.Mock()
        dst_cloud = mock.Mock()
        config = mock.Mock()
        copier = engine(src_cloud, dst_cloud, config)
        self.assertIsInstance(copier, copy_engine.RsyncCopier)

    @mock.patch("cloudferrylib.utils.drivers.copy_engine.remote_runner."
                "RemoteRunner.run")
    def test_falls_back_to_scp_if_rsync_is_not_installed(self, rr):
        host = 'host'
        user = 'user'
        password = 'password'
        config = mock.Mock()
        config.migrate.ephemeral_copy_backend = 'rsync'
        rr.side_effect = RemoteExecutionError

        engine = copy_engine.file_transfer_engine(config, host, user, password)

        self.assertTrue(inspect.isclass(engine))

        src_cloud = mock.Mock()
        dst_cloud = mock.Mock()
        config = mock.Mock()
        copier = engine(src_cloud, dst_cloud, config)
        self.assertIsInstance(copier, copy_engine.ScpCopier)
