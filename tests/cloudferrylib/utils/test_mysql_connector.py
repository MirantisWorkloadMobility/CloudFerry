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

from cloudferrylib.utils import mysql_connector
from tests import test


class GetDbTestCase(test.TestCase):
    def test_returns_mysqldump_host_if_set(self):
        config = mock.MagicMock()
        config.mysql.db_host = "db_vip"
        expected = "mysql_node"
        config.migrate.mysqldump_host = expected

        self.assertEqual(expected, mysql_connector.get_db_host(config))

    def test_returns_vip_host_if_mysqldump_node_is_not_set(self):
        config = mock.MagicMock()
        expected = "db_vip"
        config.mysql.db_host = expected
        config.migrate.mysqldump_host = None

        self.assertEqual(expected, mysql_connector.get_db_host(config))
