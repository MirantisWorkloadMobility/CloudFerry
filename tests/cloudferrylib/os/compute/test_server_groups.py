# Copyright 2014: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from novaclient.v1_1 import client as nova_client
from novaclient import exceptions as nova_exc
from oslotest import mockpatch

from cloudferrylib.os.compute import server_groups
from cloudferrylib.utils import utils

from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'region': None,
                          'auth_url': 'http://1.1.1.1:35357/v2.0/',
                          'cacert': '',
                          'insecure': False}),
    mysql=utils.ext_dict({'host': '1.1.1.1'}),
    migrate=utils.ext_dict({'migrate_quotas': True,
                            'speed_limit': '10MB',
                            'retry': '7',
                            'time_wait': 5}))


class ServerGroupTestCase(test.TestCase):

    def setUp(self):
        super(ServerGroupTestCase, self).setUp()

        self.mock_client = mock.MagicMock()
        self.nc_patch = mockpatch.PatchObject(nova_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.nc_patch)

        self.identity_mock = mock.Mock()
        self.compute_mock = mock.Mock()

        self.identity_mock.try_get_username_by_id.return_value = "user"
        self.identity_mock.try_get_tenant_name_by_id.return_value = "tenant"

        self.compute_mock.nova_client = self.mock_client
        self.mysql = mock.Mock()

        self.compute_mock.mysql_connector.execute = self.mysql

        self.fake_cloud = mock.Mock()
        self.fake_cloud.resources = dict(identity=self.identity_mock,
                                         compute=self.compute_mock)
        self.fake_cloud.position = 'src'

        self.handler = server_groups.ServerGroupsHandler(self.fake_cloud)

    def test_get_server_groups(self):
        result = mock.Mock()
        result.fetchall.side_effect = [[["u-uuid", "t-uuid", "1234", "test",
                                         1]],
                                       [["anti-affinity"]]]
        self.mysql.return_value = result
        groups = self.handler.get_server_groups()

        self.mysql.assert_any_call(server_groups.SQL_SELECT_ALL_GROUPS)

        self.assertEqual([{"user": "user",
                           "tenant": "tenant",
                           "uuid": "1234",
                           "name": "test",
                           "policies": ["anti-affinity"]}], groups)

    def test_unsupported(self):
        def raiseError():
            raise nova_exc.NotFound(404)
        self.compute_mock.nova_client.server_groups.list.side_effect = \
            raiseError

        groups = self.handler.get_server_groups()
        self.assertEqual([], groups)

    def test_deploy_server_groups_already_exists(self):
        result = mock.Mock()
        result.fetchall.side_effect = [[["u-uuid", "t-uuid", "1234", "test",
                                         1]],
                                       [["anti-affinity"]]]
        self.mysql.return_value = result

        groups = [{"user": "user",
                   "tenant": "tenant",
                   "uuid": "1234",
                   "name": "test",
                   "policies": ["anti-affinity"]}]

        self.handler._delete_server_group = mock.Mock()
        self.handler._deploy_server_group = mock.Mock()
        self.handler.deploy_server_groups(groups)

        self.assertEqual(self.handler._delete_server_group.call_count, 0)
        self.assertEqual(self.handler._deploy_server_group.call_count, 0)

    def test_deploy_server_groups_already_exists_doesnt_match(self):
        result = mock.Mock()
        result.fetchall.side_effect = [[["u-uuid", "t-uuid", "1234", "test",
                                         1]],
                                       [["anti-affinity"]]]
        self.mysql.return_value = result

        groups = [{"user": "user",
                   "tenant": "tenant",
                   "uuid": "1234",
                   "name": "test_different",
                   "policies": ["anti-affinity"]}]

        self.handler._delete_server_group = mock.Mock()
        self.handler._deploy_server_group = mock.Mock()
        self.handler.deploy_server_groups(groups)

        self.handler._delete_server_group.assert_called_once_with(
            {"user": "user",
             "tenant": "tenant",
             "uuid": "1234",
             "name": "test",
             "policies": ["anti-affinity"]}
        )
        self.handler._deploy_server_group.assert_called_once_with(groups[0])
