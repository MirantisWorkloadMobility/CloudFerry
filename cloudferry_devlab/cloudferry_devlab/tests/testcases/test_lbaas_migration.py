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

import cloudferry_devlab.tests.config as config
from cloudferry_devlab.tests import functional_test


@generator
class LBaaSMigrationTests(functional_test.FunctionalTest):
    """Test Case class which includes neutron migration cases."""

    @generate('tenant_name', 'subnet_name', 'protocol', 'lb_method')
    def test_migrate_lbaas_pools(self, param):
        """Validate load balancer pools were migrated successfuly."""
        src_lb_pools = self.replace_id_with_name(
            self.src_cloud, 'pools', self.filter_pools())
        dst_lb_pools = self.replace_id_with_name(
            self.dst_cloud, 'pools', self.dst_cloud.neutronclient.list_pools())

        self.validate_neutron_resource_parameter_in_dst(
            src_lb_pools, dst_lb_pools, resource_name='pools',
            parameter=param)

    def test_migrate_lbaas_monitors(self):
        """Validate load balancer monitors were migrated successfuly."""
        src_lb_monitors = self.replace_id_with_name(
            self.src_cloud, 'health_monitors', self.filter_health_monitors())
        dst_lb_monitors = self.replace_id_with_name(
            self.dst_cloud, 'health_monitors', self.dst_cloud.neutronclient
                .list_health_monitors())
        parameters_to_validate = ['type', 'delay', 'timeout', 'max_retries',
                                  'tenant_name']

        src_lb_monitors = self.filter_resource_parameters(
            'health_monitors', src_lb_monitors, parameters_to_validate)
        dst_lb_monitors = self.filter_resource_parameters(
            'health_monitors', dst_lb_monitors, parameters_to_validate)
        self.assertListEqual(sorted(src_lb_monitors['health_monitors']),
                             sorted(dst_lb_monitors['health_monitors']))

    def test_migrate_lbaas_members(self):
        """Validate load balancer members were migrated successfuly."""
        src_lb_members = self.replace_id_with_name(
            self.src_cloud, 'members', self.filter_lbaas_members())
        dst_lb_members = self.replace_id_with_name(
            self.dst_cloud, 'members', self.dst_cloud.neutronclient
                .list_members())
        params_to_validate = ['protocol_port', 'address', 'pool_name',
                              'tenant_name']

        src_lb_members = self.filter_resource_parameters(
            'members', src_lb_members, params_to_validate)
        dst_lb_members = self.filter_resource_parameters(
            'members', dst_lb_members, params_to_validate)
        self.assertListEqual(sorted(src_lb_members['members']),
                             sorted(dst_lb_members['members']))

    @generate('description', 'address', 'protocol', 'protocol_port',
              'connection_limit', 'pool_name', 'tenant_name', 'subnet_name')
    def test_migrate_lbaas_vips(self, param):
        """Validate load balancer vips were migrated successfuly."""
        src_lb_vips = self.replace_id_with_name(self.src_cloud, 'vips',
                                                self.filter_vips())
        dst_lb_vips = self.replace_id_with_name(self.dst_cloud, 'vips',
                                                self.dst_cloud.neutronclient.
                                                list_vips())
        self.validate_neutron_resource_parameter_in_dst(
            src_lb_vips, dst_lb_vips, resource_name='vips',
            parameter=param)

    def test_lbaas_pools_belong_deleted_tenant_not_migrate(self):
        """Validate load balancer pools in deleted tenant weren't migrated."""
        pools = []
        for tenant in config.tenants:
            if not tenant.get('deleted'):
                continue
            if tenant.get('pools'):
                pools.extend(tenant['pools'])
        pools_names = {pool['name'] for pool in pools}
        dst_pools = self.dst_cloud.neutronclient.list_pools()['pools']
        dst_pools_names = {dst_pool['name'] for dst_pool in dst_pools}
        migrated_pools = dst_pools_names.intersection(pools_names)
        if migrated_pools:
            msg = 'Lbaas pools %s belong to deleted tenant and were migrated'
            self.fail(msg % list(migrated_pools))
