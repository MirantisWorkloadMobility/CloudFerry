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
from cloudferrylib.os.compute import instances

from tests import test


class LiveMigrationTestCase(test.TestCase):
    def test_raises_error_for_unknown_migration_tool(self):
        nova_client = mock.Mock()
        config = mock.Mock()
        config.migrate.incloud_live_migration = "not-existing-migration-type"
        vm_id = "some-id"
        dest_host = "some-host"

        self.assertRaises(NotImplementedError,
                          instances.incloud_live_migrate,
                          nova_client, config, vm_id, dest_host)

    def test_runs_migration_for_nova(self):
        nova_client = mock.Mock()
        config = mock.Mock()

        config.migrate.incloud_live_migration = "nova"
        vm_id = "some-id"
        dest_host = "dest-host"

        try:
            instances.incloud_live_migrate(nova_client, config, vm_id,
                                           dest_host)
        except Exception as e:
            self.fail("Migration should not fail for nova: %s" % e)

    @mock.patch('cloudferrylib.os.compute.instances.run', mock.MagicMock())
    @mock.patch('cloudferrylib.os.compute.instances.clients', mock.MagicMock())
    def test_runs_migration_for_cobalt(self):
        nova_client = mock.Mock()
        config = mock.Mock()

        config.migrate.incloud_live_migration = "cobalt"
        vm_id = "some-id"
        dest_host = "dest-host"

        try:
            instances.incloud_live_migrate(nova_client, config, vm_id,
                                           dest_host)
        except Exception as e:
            self.fail("Migration should not fail for cobalt: %s" % e)
