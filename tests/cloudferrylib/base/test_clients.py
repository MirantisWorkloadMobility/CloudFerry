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

from cloudferrylib.base import clients

from tests import test


class ClientsTestCase(test.TestCase):
    def test_skips_region_if_not_set_in_config(self):
        config = mock.Mock()

        config.region = None
        config.tenant = 't1'
        config.user = 'user'
        config.password = 'pass'
        config.auth_url = 'auth url'

        cmd = clients.os_cli_cmd(config, 'glance', 'help')

        self.assertNotIn('--os-region', cmd)

    def test_builds_cmd_with_all_required_creds(self):
        config = mock.Mock()

        config.region = 'region1'
        config.tenant = 't1'
        config.user = 'user'
        config.password = 'pass'
        config.auth_url = 'auth url'

        client = 'glance'
        args = ['image-get', 'image-id1']

        cmd = clients.os_cli_cmd(config, client, *args)

        self.assertIn('--os-tenant-name', cmd)
        self.assertIn('--os-username', cmd)
        self.assertIn('--os-password', cmd)
        self.assertIn('--os-auth-url', cmd)
        self.assertIn('--os-region', cmd)

        self.assertTrue(cmd.startswith(client))
        self.assertTrue(cmd.endswith(" ".join(args)))
