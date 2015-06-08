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

from keystoneclient.v2_0 import client as keystone_client
from oslotest import mockpatch

from cloudferrylib.os.identity import keystone
from cloudferrylib.utils import utils
from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'auth_url': 'http://1.1.1.1:35357/v2.0/',
                          'service_tenant': 'services'}),
    migrate=utils.ext_dict({'speed_limit': '10MB',
                            'retry': '7',
                            'time_wait': 5,
                            'keep_user_passwords': False,
                            'overwrite_user_passwords': False,
                            'migrate_users': True}),
    mail=utils.ext_dict({'server': '-'}))


class KeystoneIdentityTestCase(test.TestCase):
    def setUp(self):
        super(KeystoneIdentityTestCase, self).setUp()
        self.mock_client = mock.MagicMock()
        self.kc_patch = mockpatch.PatchObject(keystone_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.kc_patch)
        self.fake_cloud = mock.Mock()
        self.fake_cloud.mysql_connector = mock.Mock()

        self.keystone_client = keystone.KeystoneIdentity(FAKE_CONFIG,
                                                         self.fake_cloud)

        self.fake_tenant_0 = mock.Mock(spec=keystone_client.tenants.Tenant)
        self.fake_tenant_0.name = 'tenant_name_0'
        self.fake_tenant_0.description = 'tenant_description_0'
        self.fake_tenant_0.id = 'tenant_id_0'
        self.fake_tenant_1 = mock.Mock(spec=keystone_client.tenants.Tenant)
        self.fake_tenant_1.name = 'tenant_name_1'
        self.fake_tenant_1.description = 'tenant_description_1'
        self.fake_tenant_1.id = 'tenant_id_1'

        self.fake_user_0 = mock.Mock(spec=keystone_client.users.User)
        self.fake_user_0.name = 'user_name_0'
        self.fake_user_0.id = 'user_id_0'
        self.fake_user_0.tenantId = self.fake_tenant_0.id
        self.fake_user_0.email = 'user0@fake.com'
        self.fake_user_1 = mock.Mock(spec=keystone_client.users.User)
        self.fake_user_1.name = 'user_name_1'
        self.fake_user_1.id = 'user_id_1'
        self.fake_user_1.tenantId = self.fake_tenant_1.id
        self.fake_user_1.email = 'user1@fake.com'

        self.fake_role_0 = mock.Mock(spec=keystone_client.roles.Role)
        self.fake_role_0.name = 'role_name_0'
        self.fake_role_0.id = 'role_id_0'
        self.fake_role_1 = mock.Mock(spec=keystone_client.roles.Role)
        self.fake_role_1.name = 'role_name_1'
        self.fake_role_1.id = 'role_id_1'

    def test_get_client(self):
        self.mock_client().auth_ref = {'token': {'id': 'fake_id'}}

        client = self.keystone_client.get_client()

        mock_calls = [
            mock.call(username='fake_user', tenant_name='fake_tenant',
                      password='fake_password',
                      auth_url='http://1.1.1.1:35357/v2.0/'),
            mock.call(token='fake_id', endpoint='http://1.1.1.1:35357/v2.0/')]
        self.mock_client.assert_has_calls(mock_calls, any_order=True)
        self.assertEqual(self.mock_client(), client)

    def test_get_tenants_list(self):
        fake_tenants_list = [self.fake_tenant_0, self.fake_tenant_1]
        self.mock_client().tenants.list.return_value = fake_tenants_list

        tenant_list = self.keystone_client.get_tenants_list()

        self.assertEqual(fake_tenants_list, tenant_list)

    def test_get_tenant_by_name(self):
        fake_tenants_list = [self.fake_tenant_0, self.fake_tenant_1]
        self.mock_client().tenants.list.return_value = fake_tenants_list

        tenant = self.keystone_client.get_tenant_by_name('tenant_name_0')

        self.assertEqual(self.fake_tenant_0, tenant)

    def test_get_tenant_by_name_default(self):
        self.mock_client().tenants.list.return_value = []

        tenant = self.keystone_client.get_tenant_by_name('tenant_name_0')

        self.assertIsNone(tenant)

    def test_get_tenant_by_id(self):
        self.mock_client().tenants.get.return_value = self.fake_tenant_0

        tenant = self.keystone_client.get_tenant_by_id('tenant_id_0')

        self.assertEqual(self.fake_tenant_0, tenant)

    def test_get_users_list(self):
        fake_users_list = [self.fake_user_0, self.fake_user_1]
        self.mock_client().users.list.return_value = fake_users_list

        users_list = self.keystone_client.get_users_list()

        self.assertEqual(fake_users_list, users_list)

    def test_get_roles_list(self):
        fake_roles_list = ['fake_role_0', 'fake_role_1']
        self.mock_client().roles.list.return_value = fake_roles_list

        roles_list = self.keystone_client.get_roles_list()

        self.assertEqual(fake_roles_list, roles_list)

    def test_create_role(self):
        self.keystone_client.create_role('fake_role')

        self.mock_client().roles.create.assert_called_once_with('fake_role')

    def test_create_tenant(self):
        self.keystone_client.create_tenant('fake_tenant_name')

        test_args = {'tenant_name': 'fake_tenant_name',
                     'enabled': True,
                     'description': None}
        self.mock_client().tenants.create.assert_called_once_with(**test_args)

    def test_create_user(self):
        self.keystone_client.create_user('fake_user')

        test_args = {'name': 'fake_user',
                     'password': None,
                     'email': None,
                     'enabled': True,
                     'tenant_id': None}
        self.mock_client().users.create.assert_called_once_with(**test_args)

    def test_update_tenant(self):
        self.keystone_client.update_tenant(tenant_id='tenant_id',
                                           tenant_name='new_fake_tenant_name')

        test_args = {'tenant_name': 'new_fake_tenant_name',
                     'enabled': None,
                     'description': None}
        self.mock_client().tenants.update.assert_called_once_with('tenant_id',
                                                                  **test_args)

    def test_update_user(self):
        self.keystone_client.update_user(self.fake_user_0,
                                         name='fake_new_user',
                                         email='fake@gmail.com',
                                         enabled=False)

        test_args = {'name': 'fake_new_user',
                     'email': 'fake@gmail.com',
                     'enabled': False}

        self.mock_client().users.update.assert_called_once_with(
            self.fake_user_0,
            **test_args)

    def test_auth_token_from_user(self):
        fake_auth_token = 'fake_auth_token'
        self.mock_client().auth_token_from_user = fake_auth_token

        self.assertEquals(fake_auth_token,
                          self.keystone_client.get_auth_token_from_user())

    def test_read_info(self):
        fake_tenants_list = [self.fake_tenant_0, self.fake_tenant_1]
        fake_users_list = [self.fake_user_0, self.fake_user_1]
        fake_roles_list = [self.fake_role_0, self.fake_role_1]
        fake_info = self._get_fake_info(fake_tenants_list, fake_users_list,
                                        fake_roles_list)

        self.mock_client().tenants.list.return_value = fake_tenants_list
        self.mock_client().users.list.return_value = fake_users_list
        self.mock_client().roles.list.return_value = fake_roles_list
        self.mock_client().roles.roles_for_user.return_value = [
            self.fake_role_0]

        info = self.keystone_client.read_info()

        self.assertEquals(fake_info, info)

    def test_deploy(self):
        fake_tenants_list = [self.fake_tenant_0, self.fake_tenant_1]
        fake_users_list = [self.fake_user_0, self.fake_user_1]
        fake_roles_list = [self.fake_role_0, self.fake_role_1]
        fake_info = self._get_fake_info(fake_tenants_list, fake_users_list,
                                        fake_roles_list)

        self.mock_client().tenants.list.return_value = [fake_tenants_list[0]]
        self.mock_client().users.list.return_value = [fake_users_list[0]]
        self.mock_client().roles.list.return_value = [fake_roles_list[0]]
        self.mock_client().roles.roles_for_user.return_value = [
            self.fake_role_1]

        def tenant_create(**kwargs):
            self.mock_client().tenants.list.return_value.append(
                fake_tenants_list[1])
            return fake_tenants_list[1]

        def user_create(**kwars):
            self.mock_client().users.list.return_value.append(
                fake_users_list[1])
            return fake_users_list[1]

        def roles_create(role_name):
            self.mock_client().roles.list.return_value.append(
                fake_roles_list[1])
            return fake_roles_list[1]

        self.mock_client().tenants.create = tenant_create
        self.mock_client().users.create = user_create
        self.mock_client().roles.create = roles_create

        self.keystone_client.deploy(fake_info)

        mock_calls = []
        for user in fake_users_list:
            for tenant in fake_tenants_list:
                mock_calls.append(
                    mock.call(user.id, fake_roles_list[0].id, tenant.id))

        self.assertEquals(mock_calls,
                          self.mock_client().roles.add_user_role.mock_calls)

    @staticmethod
    def _get_fake_info(fake_tenants_list, fake_users_list, fake_roles_list):
        fake_user_tenants_roles = {}
        for user in fake_users_list:
            fake_user_tenants_roles[user.name] = {}
            for tenant in fake_tenants_list:
                fake_user_tenants_roles[user.name][
                    tenant.name] = [{'role': {'name': fake_roles_list[0].name,
                                              'id': fake_roles_list[0].id}}]

        fake_info = {'tenants': [],
                     'users': [],
                     'roles': [],
                     'user_tenants_roles': fake_user_tenants_roles}

        for tenant in fake_tenants_list:
            fake_info['tenants'].append(
                {'tenant': {'name': tenant.name,
                            'id': tenant.id,
                            'description': tenant.description},
                 'meta': {}})

        for user in fake_users_list:
            fake_info['users'].append(
                {'user': {'name': user.name,
                          'id': user.id,
                          'email': user.email,
                          'tenantId': user.tenantId},
                 'meta': {'overwrite_password': False}})

        for role in fake_roles_list:
            fake_info['roles'].append(
                {'role': {'name': role.name,
                          'id': role},
                 'meta': {}})
        return fake_info
