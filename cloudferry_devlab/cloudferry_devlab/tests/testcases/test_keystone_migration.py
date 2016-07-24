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

from generator import generator, generate
from nose.plugins.attrib import attr

from cloudferry_devlab.tests import functional_test
import cloudferry_devlab.tests.config as config
import cloudferry_devlab.tests.base as base


@generator
class KeystoneMigrationTests(functional_test.FunctionalTest):
    """Test Case class which includes keystone resources migration cases."""

    def setUp(self):
        super(KeystoneMigrationTests, self).setUp()
        self.src_users = self.filter_users()
        self.dst_users = self.dst_cloud.keystoneclient.users.list()

    @generate('name', 'email', 'enabled')
    def test_migrate_keystone_users(self, param):
        """Validate users were migrated with correct name and email.

        :param name: user's name
        :param description: user's description
        :param enabled: is user enabled"""
        filtered_src_users = [user for user in self.src_users
                              if getattr(user, "name") !=
                              config.case_sensitivity_test_user]
        self.validate_resource_parameter_in_dst(filtered_src_users,
                                                self.dst_users,
                                                resource_name='user',
                                                parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2',
          config.case_sensitivity_test_tenant])
    def test_migrate_keystone_user_tenant_roles(self):
        """Validate user's tenant roles were migrated with correct name."""
        tenant = base.get_nosetest_cmd_attribute_val('migrated_tenant')
        dst_tenant = self.migration_utils.check_mapped_tenant(
            tenant_name=tenant)
        for dst_user in self.dst_users:
            src_user = None
            for user in self.src_users:
                if user.name.lower() == dst_user.name.lower():
                    src_user = user
                    break
            if src_user is None:
                continue
            if tenant is None:
                src_user_tnt_roles = self.src_cloud.get_user_tenant_roles(
                                         src_user)
                dst_user_tnt_roles = self.dst_cloud.get_user_tenant_roles(
                                         dst_user)
            else:
                src_user_tnt_roles = self.src_cloud.get_roles_for_user(
                                         src_user, tenant)
                dst_user_tnt_roles = self.dst_cloud.get_roles_for_user(
                                         dst_user, dst_tenant)
            if len(src_user_tnt_roles) == 0 and len(dst_user_tnt_roles) == 0:
                continue
            self.validate_resource_parameter_in_dst(
                src_user_tnt_roles, dst_user_tnt_roles,
                resource_name='user_tenant_role', parameter='name')

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2',
          config.case_sensitivity_test_tenant])
    @generate('name', 'description', 'enabled')
    def test_migrate_keystone_roles(self, param):
        """Validate user's roles were migrated with correct parameters.

        :param name: role's name
        :param description: role's description
        :param enabled: is role enabled
        """
        src_roles = self.filter_roles()
        dst_roles = self.dst_cloud.keystoneclient.roles.list()

        self.validate_resource_parameter_in_dst(src_roles, dst_roles,
                                                resource_name='role',
                                                parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2',
          config.case_sensitivity_test_tenant])
    @generate('name', 'description', 'enabled')
    def test_migrate_keystone_tenants(self, param):
        """Validate tenants were migrated with correct name and description.

        :param name: tenant's name
        :param description: tenant's description
        :param enabled: is tenant enabled"""
        src_tenants = self.filter_tenants()
        dst_tenants_gen = self.dst_cloud.keystoneclient.tenants.list()
        dst_tenants = [x for x in dst_tenants_gen]

        filtering_data = self.filtering_utils.filter_tenants(src_tenants)
        src_tenants = filtering_data[0]
        src_tenants = [tenant for tenant in src_tenants
                       if getattr(tenant, "name") !=
                       config.case_sensitivity_test_tenant and
                       getattr(tenant, "name") not in
                       config.mapped_tenant_dict.keys()]

        self.validate_resource_parameter_in_dst(src_tenants, dst_tenants,
                                                resource_name='tenant',
                                                parameter=param)
