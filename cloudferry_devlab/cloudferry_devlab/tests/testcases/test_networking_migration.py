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

import pprint
import unittest

from generator import generator, generate
from nose.plugins.attrib import attr

from cloudferry_devlab.tests import functional_test


@generator
class NetrworkingMigrationTests(functional_test.FunctionalTest):
    """Test Case class which includes neutron migration cases."""

    def setUp(self):
        super(NetrworkingMigrationTests, self).setUp()
        self.src_routers = self.filter_routers()['routers']
        self.dst_routers = self.dst_cloud.neutronclient.list_routers()[
            'routers']

    def validate_network_name_in_port_lists(self, src_ports, dst_ports):
        dst_net_names = [self.dst_cloud.get_net_name(dst_port['network_id'])
                         for dst_port in dst_ports]
        src_net_names = [self.src_cloud.get_net_name(src_port['network_id'])
                         for src_port in src_ports]
        self.assertTrue(dst_net_names.sort() == src_net_names.sort(),
                        msg="Network ports is not the same. SRC: %s \n DST: %s"
                            % (src_net_names, dst_net_names))

    @generate('name', 'provider:network_type', 'provider:segmentation_id',
              'provider:physical_network', 'status', 'admin_state_up',
              'router:external', 'shared')
    def test_migrate_neutron_networks(self, param):
        """Validate networks were migrated with correct parameters.

        :param name:
        :param provider\\:network_type:
        :param provider\\:segmentation_id:
        :param provider\\:physical_network:
        :param status:
        :param admin_state_up:
        :param router\\:external:
        :param shared:"""
        src_nets = self.filter_networks()
        dst_nets = self.dst_cloud.neutronclient.list_networks()

        self.validate_neutron_resource_parameter_in_dst(src_nets, dst_nets,
                                                        parameter=param)

    @generate('name', 'gateway_ip', 'cidr', 'dns_nameservers', 'enable_dhcp',
              'allocation_pools', 'host_routes', 'ip_version')
    def test_migrate_neutron_subnets(self, param):
        """Validate subnets were migrated with correct parameters.

        :param name:
        :param gateway_ip:
        :param cidr:
        :param dns_nameservers:
        :param enable_dhcp:
        :param allocation_pools:
        :param host_routes:
        :param ip_version:"""
        src_subnets = self.filter_subnets()
        dst_subnets = self.dst_cloud.neutronclient.list_subnets()

        self.validate_neutron_resource_parameter_in_dst(
            src_subnets, dst_subnets, resource_name='subnets',
            parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    @generate('name', 'external_gateway_info', 'status', 'admin_state_up',
              'routes')
    def test_migrate_neutron_routers(self, param):
        """Validate routers were migrated with correct parameters.

        :param name:
        :param external_gateway_info:"""

        def format_external_gateway_info(client, info):
            """ Method replaces network id with network name and deletes all
            attributes except enable_snat and network_name
            """
            _info = {'network_name': client.neutronclient.show_network(
                info['network_id'])['network']['name']}
            if check_snat:
                _info['enable_snat'] = info['enable_snat']
            return _info

        if param == 'external_gateway_info':
            # check, do src and dst clouds support snat
            check_snat = {self.src_cloud.openstack_release,
                          self.dst_cloud.openstack_release}.issubset(
                {'icehouse', 'juno'})
            for src_router in self.src_routers:
                src_router['external_gateway_info'] = \
                    format_external_gateway_info(
                        self.src_cloud, src_router['external_gateway_info'])
            for dst_router in self.dst_routers:
                dst_router['external_gateway_info'] = \
                    format_external_gateway_info(
                        self.dst_cloud, dst_router['external_gateway_info'])
        self.validate_neutron_resource_parameter_in_dst(
            {'routers': self.src_routers}, {'routers': self.dst_routers},
            resource_name='routers', parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_validate_router_migrated_once(self):
        """Validate routers were migrated just one time."""
        src_routers_names = [router['name'] for router
                             in self.src_routers]
        dst_routers_names = [router['name'] for router
                             in self.dst_routers]
        router_migrated_more_than_once = [r for r in src_routers_names if
                                          dst_routers_names.count(r) > 1]
        if router_migrated_more_than_once:
            self.fail(msg='Routers %s presents multiple times' %
                          router_migrated_more_than_once)

    @attr(migrated_tenant=['tenant1', 'tenant2'])
    def test_router_connected_to_correct_networks(self):
        """Validate routers were connected to correct network on dst."""
        for dst_router in self.dst_routers:
            dst_ports = self.dst_cloud.neutronclient.list_ports(
                retrieve_all=True, **{'device_id': dst_router['id']})['ports']
            for src_router in self.src_routers:
                if src_router['name'] == dst_router['name']:
                    src_ports = self.src_cloud.neutronclient.list_ports(
                        retrieve_all=True,
                        **{'device_id': src_router['id']})['ports']
                    self.validate_network_name_in_port_lists(
                        src_ports=src_ports, dst_ports=dst_ports)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_router_migrated_to_correct_tenant(self):
        """Validate routers were migrated to correct tenant on dst."""
        for dst_router in self.dst_routers:
            dst_tenant_name = self.dst_cloud.get_tenant_name(
                dst_router['tenant_id'])
            for src_router in self.src_routers:
                if src_router['name'] == dst_router['name']:
                    src_tenant_name = self.src_cloud.get_tenant_name(
                        src_router['tenant_id'])
                    src_tenant_name = self.migration_utils.check_mapped_tenant(
                        tenant_name=src_tenant_name)
                    self.assertTrue(src_tenant_name == dst_tenant_name,
                                    msg='DST tenant name %s is not equal to '
                                        'SRC %s' %
                                        (dst_tenant_name, src_tenant_name))

    @generate('name', 'description')
    def test_migrate_security_groups(self, param):
        """Validate security groups were migrated with correct parameters.

        :param name: name of the security group
        :param description: description of specific security group"""
        src_sec_gr = self.filter_security_groups()
        dst_sec_gr = self.dst_cloud.neutronclient.list_security_groups()
        self.validate_neutron_resource_parameter_in_dst(
            src_sec_gr, dst_sec_gr, resource_name='security_groups',
            parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_floating_ips_migrated(self):
        """Validate floating IPs were migrated correctly."""

        def get_fips(client):
            return set([fip['floating_ip_address']
                        for fip in client.list_floatingips()['floatingips']])

        src_fips = self.filter_floatingips()
        dst_fips = get_fips(self.dst_cloud.neutronclient)

        missing_fips = src_fips - dst_fips

        if missing_fips:
            self.fail("{num} floating IPs did not migrate to destination: "
                      "{fips}".format(num=len(missing_fips),
                                      fips=pprint.pformat(missing_fips)))

    @unittest.skipIf(functional_test.get_option_from_config_ini(
        option='change_router_ips') == 'False',
        'Change router ips disabled in CloudFerry config')
    def test_ext_router_ip_changed(self):
        """Validate router IPs were changed after migration."""
        dst_routers = self.dst_cloud.get_ext_routers()
        src_routers = self.src_cloud.get_ext_routers()
        routers_with_same_gateway = []
        for dst_router in dst_routers:
            for src_router in src_routers:
                if dst_router['name'] != src_router['name']:
                    continue
                src_gateway = self.src_cloud.neutronclient.list_ports(
                    device_id=src_router['id'],
                    device_owner='network:router_gateway')['ports'][0]
                dst_gateway = self.dst_cloud.neutronclient.list_ports(
                    device_id=dst_router['id'],
                    device_owner='network:router_gateway')['ports'][0]
                if src_gateway['fixed_ips'][0]['ip_address'] == \
                        dst_gateway['fixed_ips'][0]['ip_address']:
                    routers_with_same_gateway.append((dst_router['name'],
                                                      dst_gateway['fixed_ips']
                                                      [0]['ip_address']))
        if routers_with_same_gateway:
            self.fail(msg='GW ip addresses of routers "{0}" are same on src '
                          'and dst: {1}'.format([x[0] for x in
                                                 routers_with_same_gateway],
                                                [x[1] for x in
                                                 routers_with_same_gateway]))
