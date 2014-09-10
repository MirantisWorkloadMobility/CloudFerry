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

from cloudferrylib.os.identity import keystone
from tests import test
from oslotest import mockpatch

from keystoneclient.v2_0 import client as keystone_client


FAKE_CONFIG = {'user': 'fake_user',
               'password': 'fake_password',
               'tenant': 'fake_tenant',
               'host': '1.1.1.1'}


class KeystoneIdentityTestCase(test.TestCase):
    def setUp(self):
        super(KeystoneIdentityTestCase, self).setUp()
        self.mock_client = mock.MagicMock()
        self.kc_patch = mockpatch.PatchObject(keystone_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.kc_patch)
        self.keystone_client = keystone.KeystoneIdentity(FAKE_CONFIG)

        self.fake_user = mock.Mock()
        self.fake_user_0 = mock.Mock()

        self.fake_tenant_0 = mock.Mock()
        self.fake_tenant_0.name = 'fake_name'
        self.fake_tenant_1 = mock.Mock()

        self.fake_service_0 = mock.Mock()
        self.fake_service_1 = mock.Mock()
        self.fake_service_0.type = 'fake_type'
        self.fake_service_0.name = 'fake_name'
        self.fake_service_0.id = 'fake_id'

        self.fake_endpoint_0 = mock.Mock()
        self.fake_endpoint_1 = mock.Mock()
        self.fake_endpoint_0.service_id = 'fake_id'
        self.fake_endpoint_0.publicurl = 'example.com'

    def test_get_client(self):
        self.mock_client().auth_ref = {'token': {'id': 'fake_id'}}

        client = self.keystone_client.get_client()

        mock_calls = [
            mock.call(username='fake_user', tenant_name='fake_tenant',
                      password='fake_password',
                      auth_url='http://1.1.1.1:35357/v2.0/'),
            mock.call(token='fake_id', endpoint='http://1.1.1.1:35357/v2.0/')]
        self.mock_client.assert_has_calls(mock_calls)
        self.assertEqual(self.mock_client(), client)

    def test_get_tenants_list(self):
        fake_tenants_list = [self.fake_tenant_0, self.fake_tenant_1]
        self.mock_client().tenants.list.return_value = fake_tenants_list

        tenant_list = self.keystone_client.get_tenants_list()

        self.assertEqual(fake_tenants_list, tenant_list)

    def test_get_services_list(self):
        fake_services_list = [self.fake_service_0, self.fake_service_1]
        self.mock_client().services.list.return_value = fake_services_list

        services_list = self.keystone_client.get_services_list()

        self.assertEqual(fake_services_list, services_list)

    def test_get_service_name_by_type(self):
        fake_services_list = [self.fake_service_0, self.fake_service_1]
        self.mock_client().services.list.return_value = fake_services_list

        service_name = self.keystone_client.get_service_name_by_type(
            'fake_type')

        self.assertEqual('fake_name', service_name)

    def test_get_service_name_by_type_default(self):
        self.mock_client().services.list.return_value = []

        service_name = self.keystone_client.get_service_name_by_type(
            'fake_type')

        self.assertEqual('nova', service_name)

    def test_get_public_endpoint_service_by_id(self):
        fake_endpoints_list = [self.fake_endpoint_0, self.fake_endpoint_1]
        self.mock_client().endpoints.list.return_value = fake_endpoints_list

        endpoint = self.keystone_client.get_public_endpoint_service_by_id(
            'fake_id')

        self.assertEqual('example.com', endpoint)

    def test_get_public_endpoint_service_by_id_default(self):
        self.mock_client().endpoints.list.return_value = []

        endpoint = self.keystone_client.get_public_endpoint_service_by_id(
            'fake_service_id')

        self.assertIsNone(endpoint)

    def test_get_service_id(self):
        fake_services_list = [self.fake_service_0, self.fake_service_1]
        self.mock_client().services.list.return_value = fake_services_list

        service_id = self.keystone_client.get_service_id('fake_name')

        self.assertEqual('fake_id', service_id)

    def test_get_service_id_default(self):
        self.mock_client().services.list.return_value = []

        service_id = self.keystone_client.get_service_id('fake_name')

        self.assertIsNone(service_id)

    def test_get_endpoint_by_service_name(self):
        fake_services_list = [self.fake_service_0, self.fake_service_1]
        self.mock_client().services.list.return_value = fake_services_list

        fake_endpoints_list = [self.fake_endpoint_0, self.fake_endpoint_1]
        self.mock_client().endpoints.list.return_value = fake_endpoints_list

        endpoint = self.keystone_client.get_endpoint_by_service_name(
            'fake_name')

        self.assertEqual('example.com', endpoint)

    def test_get_tenant_by_name(self):
        fake_tenants_list = [self.fake_tenant_0, self.fake_tenant_1]
        self.mock_client().tenants.list.return_value = fake_tenants_list

        tenant = self.keystone_client.get_tenant_by_name('fake_name')

        self.assertEqual(self.fake_tenant_0, tenant)

    def test_get_tenant_by_name_default(self):
        self.mock_client().tenants.list.return_value = []

        tenant = self.keystone_client.get_tenant_by_name('fake_name')

        self.assertIsNone(tenant)

    def test_get_tenant_by_id(self):
        self.mock_client().tenants.get.return_value = self.fake_tenant_0

        tenant = self.keystone_client.get_tenant_by_id('fake_id')

        self.assertEqual(self.fake_tenant_0, tenant)

    def test_get_users_list(self):
        fake_users_list = [self.fake_user, self.fake_user_0]
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
        self.keystone_client.update_user(self.fake_user, name='fake_new_user',
                                         email='fake@gmail.com', enabled=False)

        test_args = {'name': 'fake_new_user',
                     'email': 'fake@gmail.com',
                     'enabled': False}

        self.mock_client().users.update.assert_called_once_with(self.fake_user,
                                                                **test_args)

    def test_auth_token_from_user(self):
        fake_auth_token = 'fake_auth_token'
        self.mock_client().auth_token_from_user = fake_auth_token

        self.assertEquals(fake_auth_token,
                          self.keystone_client.get_auth_token_from_user())
