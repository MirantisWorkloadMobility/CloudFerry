# Copyright (c) 2015 Mirantis Inc.
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

import unittest

from generator import generator, generate
from nose.plugins.attrib import attr

from cloudferry_devlab.tests import functional_test


@generator
class NovaResourceMigrationTests(functional_test.FunctionalTest):
    """
    Test Case class which includes all resource's migration cases.
    """

    @generate('name', 'fingerprint', 'public_key')
    def test_migrate_nova_keypairs(self, param):
        """Validate keypairs were migrated with correct parameters.
        :param name: name of the keypair
        :param fingerprint: keypair's fingerptint
        :param public_key: public key of the keypair"""
        src_keypairs = self.filter_keypairs()
        dst_keypairs = self.dst_cloud.get_users_keypairs()

        self.validate_resource_parameter_in_dst(src_keypairs, dst_keypairs,
                                                resource_name='keypair',
                                                parameter=param)

    @unittest.skipIf(functional_test.get_option_from_config_ini(
        option='keep_affinity_settings') == 'False',
        'Keep affinity settings disabled in CloudFerry config')
    @attr(migrated_tenant=['tenant1', 'tenant2', 'tenant4'])
    def test_migrate_nova_server_groups(self):
        """Validate server groups were migrated with correct parameters.

        :param name: server group name
        :param members: servers in the current group"""
        def get_members_names(client, sg_groups):
            groups = {}
            for sg_group in sg_groups:
                members_names = [client.servers.get(member).name
                                 for member in sg_group.members]
                groups[sg_group.name] = sorted(members_names)
            return groups

        if self.src_cloud.openstack_release == 'grizzly':
            self.skipTest('Grizzly release does not support server groups')
        src_server_groups = self.src_cloud.get_all_server_groups()
        dst_server_groups = self.dst_cloud.get_all_server_groups()
        self.validate_resource_parameter_in_dst(
            src_server_groups, dst_server_groups,
            resource_name='server_groups',
            parameter='name')
        src_members = get_members_names(self.src_cloud.novaclient,
                                        src_server_groups)
        dst_members = get_members_names(self.dst_cloud.novaclient,
                                        dst_server_groups)
        for group in src_members:
            self.assertListEqual(src_members[group], dst_members[group],
                                 'Members in server group: "{0}" are different'
                                 ': "{1}" and "{2}"'.format(group,
                                                            src_members[group],
                                                            dst_members[group])
                                 )

    @generate('nova_q', 'neutron_q', 'cinder_q')
    def test_migrate_tenant_quotas(self, param):
        """Validate tenant's quotas were migrated to correct tenant.

        Scenario:
            1. Get nova quota parameters from src cloud
            2. Get neutron quota parameters from src cloud
            3. Get cinder quota parameters, common for src and dst clouds
            4. Get nova, neutron and cinder quotas values for each tenant from
                src cloud
            5. Get nova, neutron and cinder quotas values for each tenant from
                dst cloud
            6. Verify nova tenant quotas the same on dst and src clouds
            7. Verify neutron tenant quotas the same on dst and src clouds
            8. Verify cinder tenant quotas the same on dst and src clouds
        """

        def get_tenant_quotas(tenants, client):
            """
            Method gets nova and neutron quotas for given tenants, and saves
            quotas, which are exist on src (on dst could exists quotas, which
            are not exist on src).
            """
            qs = {}
            for t in tenants:
                qs[t.name.lower()] = {'nova_q': {}, 'neutron_q': {},
                                      'cinder_q': {}}
                nova_quota = client.novaclient.quotas.get(t.id).to_dict()
                for k, v in nova_quota.iteritems():
                    if k in src_nova_quota_keys and k != 'id':
                        qs[t.name.lower()]['nova_q'][k] = v
                neutron_quota = client.neutronclient.show_quota(t.id)['quota']
                for k, v in neutron_quota.iteritems():
                    if k in src_neutron_quota_keys:
                        qs[t.name.lower()]['neutron_q'][k] = v
                cinder_quota = getattr(client.cinderclient.quotas.get(t.id),
                                       '_info')
                for k, v in cinder_quota.iteritems():
                    if k in cinder_quota_keys and k != 'id':
                        qs[t.name.lower()]['cinder_q'][k] = v
            return qs

        src_nova_quota_keys = self.src_cloud.novaclient.quotas.get(
            self.src_cloud.keystoneclient.tenant_id).to_dict().keys()
        src_neutron_quota_keys = self.src_cloud.neutronclient.show_quota(
            self.src_cloud.keystoneclient.tenant_id)['quota'].keys()
        src_cinder_q_keys = getattr(self.src_cloud.cinderclient.quotas.get(
            self.src_cloud.keystoneclient.tenant_id), '_info').keys()
        dst_cinder_q_keys = getattr(self.dst_cloud.cinderclient.quotas.get(
            self.dst_cloud.keystoneclient.tenant_id), '_info').keys()
        cinder_quota_keys = set(src_cinder_q_keys) & set(dst_cinder_q_keys)

        src_quotas = get_tenant_quotas(self.filter_tenants(), self.src_cloud)
        dst_quotas = get_tenant_quotas(
            self.dst_cloud.keystoneclient.tenants.list(), self.dst_cloud)
        tenants_with_missed_quotas = []
        for tenant in src_quotas:
            self.assertIn(tenant, dst_quotas,
                          'Tenant %s is missing on dst' % tenant)
            if src_quotas[tenant][param] != dst_quotas[tenant][param]:
                tenants_with_missed_quotas.append(tenant)
        if tenants_with_missed_quotas:
            self.fail(msg='%s quotas for tenants %s migrated not successfully'
                          % (param, tenants_with_missed_quotas))
