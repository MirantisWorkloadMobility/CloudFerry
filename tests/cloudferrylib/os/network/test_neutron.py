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


import copy
import mock

from neutronclient.v2_0 import client as neutron_client
from oslotest import mockpatch

from cloudferrylib.os.network import neutron
from cloudferrylib.utils import utils
from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'auth_url': 'http://1.1.1.1:35357/v2.0/',
                          'service_tenant': 'services'}),
    migrate=utils.ext_dict({'ext_net_map': 'fake_ext_net_map.yaml',
                            'speed_limit': '10MB',
                            'retry': '7',
                            'time_wait': 5}))


class NeutronTestCase(test.TestCase):

    def setUp(self):
        super(NeutronTestCase, self).setUp()

        self.neutron_mock_client = mock.MagicMock()

        self.neutron_client_patch = \
            mockpatch.PatchObject(neutron_client,
                                  'Client',
                                  new=self.neutron_mock_client)
        self.useFixture(self.neutron_client_patch)
        self.identity_mock = mock.Mock()
        self.network_mock = mock.Mock()
        self.network_mock.neutron_client = self.neutron_mock_client
        self.fake_cloud = mock.Mock()
        self.fake_cloud.mysql_connector = mock.Mock()
        self.fake_cloud.resources = dict(identity=self.identity_mock,
                                         network=self.network_mock)

        self.neutron_network_client = \
            neutron.NeutronNetwork(FAKE_CONFIG, self.fake_cloud)

        self.identity_mock.get_tenant_id_by_name = self.f_tenant_id_by_name
        self.identity_mock.get_tenants_func = \
            mock.Mock(return_value=self.f_mock)

        self.net_1_info = {'name': 'fake_network_name_1',
                           'id': 'fake_network_id_1',
                           'admin_state_up': True,
                           'shared': False,
                           'tenant_id': 'fake_tenant_id_1',
                           'tenant_name': 'fake_tenant_name_1',
                           'subnet_names': ['fake_subnet_name_1'],
                           'router:external': False,
                           'provider:physical_network': None,
                           'provider:network_type': 'gre',
                           'provider:segmentation_id': 5,
                           'res_hash': 'fake_net_hash_1',
                           'meta': {}}

        self.net_2_info = {'name': 'fake_network_name_2',
                           'id': 'fake_network_id_2',
                           'admin_state_up': True,
                           'shared': False,
                           'tenant_id': 'fake_tenant_id_2',
                           'tenant_name': 'fake_tenant_name_2',
                           'subnet_names': ['fake_subnet_name_2'],
                           'router:external': False,
                           'provider:physical_network': None,
                           'provider:network_type': 'gre',
                           'provider:segmentation_id': 10,
                           'res_hash': 'fake_net_hash_2',
                           'meta': {}}

        self.subnet_1_info = {'name': 'fake_subnet_name_1',
                              'id': 'fake_subnet_id_1',
                              'enable_dhcp': True,
                              'allocation_pools': [{'start': 'fake_start_ip_1',
                                                    'end': 'fake_end_ip_1'}],
                              'gateway_ip': 'fake_gateway_ip_1',
                              'ip_version': 4,
                              'cidr': 'fake_cidr_1',
                              'network_name': 'fake_network_name_1',
                              'external': False,
                              'network_id': 'fake_network_id_1',
                              'tenant_name': 'fake_tenant_name_1',
                              'res_hash': 'fake_subnet_hash_1',
                              'meta': {}}

        self.subnet_2_info = {'name': 'fake_subnet_name_2',
                              'id': 'fake_subnet_id_2',
                              'enable_dhcp': True,
                              'allocation_pools': [{'start': 'fake_start_ip_2',
                                                    'end': 'fake_end_ip_2'}],
                              'gateway_ip': 'fake_gateway_ip_2',
                              'ip_version': 4,
                              'cidr': 'fake_cidr_2',
                              'network_name': 'fake_network_name_2',
                              'external': False,
                              'network_id': 'fake_network_id_2',
                              'tenant_name': 'fake_tenant_name_2',
                              'res_hash': 'fake_subnet_hash_2',
                              'meta': {}}

    def f_mock(self, tenant_id):
        if tenant_id == 'fake_tenant_id_1':
            return 'fake_tenant_name_1'
        elif tenant_id == 'fake_tenant_id_2':
            return 'fake_tenant_name_2'

    def f_tenant_id_by_name(self, name):
        if name == 'fake_tenant_name_1':
            return 'fake_tenant_id_1'
        elif name == 'fake_tenant_name_2':
            return 'fake_tenant_id_2'

    def test_get_client(self):
        # To check self.mock_client call only from this test method
        self.neutron_mock_client.reset_mock()

        client = self.neutron_network_client.get_client()

        self.neutron_mock_client.assert_called_once_with(
            username='fake_user',
            password='fake_password',
            tenant_name='fake_tenant',
            auth_url='http://1.1.1.1:35357/v2.0/'
        )
        self.assertEqual(self.neutron_mock_client(), client)

    def test_get_networks(self):

        fake_networks_list = {'networks': [{'status': 'ACTIVE',
                                            'subnets': ['fake_subnet_id_1'],
                                            'name': 'fake_network_name_1',
                                            'provider:physical_network': None,
                                            'admin_state_up': True,
                                            'tenant_id': 'fake_tenant_id_1',
                                            'provider:network_type': 'gre',
                                            'router:external': False,
                                            'shared': False,
                                            'id': 'fake_network_id_1',
                                            'provider:segmentation_id': 5}]}

        self.neutron_mock_client().list_networks.return_value = \
            fake_networks_list
        self.neutron_mock_client.show_subnet.return_value = \
            {'subnet': {'name': 'fake_subnet_name_1'}}
        self.network_mock.get_resource_hash = \
            mock.Mock(return_value='fake_net_hash_1')

        networks_info = [self.net_1_info]
        networks_info_result = self.neutron_network_client.get_networks()
        self.assertEquals(networks_info, networks_info_result)

    def test_get_subnets(self):

        fake_subnets_list = {
            'subnets': [{'name': 'fake_subnet_name_1',
                         'enable_dhcp': True,
                         'network_id': 'fake_network_id_1',
                         'tenant_id': 'fake_tenant_id_1',
                         'allocation_pools': [
                             {'start': 'fake_start_ip_1',
                              'end': 'fake_end_ip_1'}
                         ],
                         'host_routes': [],
                         'ip_version': 4,
                         'gateway_ip': 'fake_gateway_ip_1',
                         'cidr': 'fake_cidr_1',
                         'id': 'fake_subnet_id_1'}]}

        self.neutron_mock_client().list_subnets.return_value = \
            fake_subnets_list
        self.neutron_mock_client.show_network.return_value = \
            {'network': {'name': 'fake_network_name_1',
                         'router:external': False}}
        self.network_mock.get_resource_hash = \
            mock.Mock(return_value='fake_subnet_hash_1')

        subnets_info = [self.subnet_1_info]
        subnets_info_result = self.neutron_network_client.get_subnets()
        self.assertEquals(subnets_info, subnets_info_result)

    def test_get_routers(self):

        fake_routers_list = {
            'routers': [{'status': 'ACTIVE',
                         'external_gateway_info': {
                             'network_id': 'fake_network_id_1',
                             'enable_snat': True
                         },
                         'name': 'fake_router_name_1',
                         'admin_state_up': True,
                         'tenant_id': 'fake_tenant_id_1',
                         'routes': [],
                         'id': 'fake_router_id_1'}]}

        self.neutron_mock_client().list_routers.return_value = \
            fake_routers_list
        self.neutron_mock_client.show_network.return_value = \
            {'network': {'name': 'fake_network_name_1',
                         'tenant_id': 'fake_tenant_id_1'}}

        fake_ports_list = {
            'ports': [{'fixed_ips': [{'subnet_id': 'fake_subnet_id_1',
                                      'ip_address': 'fake_ipaddr_1'}],
                       'device_id': 'fake_router_id_1'}]}

        self.neutron_mock_client.list_ports.return_value = fake_ports_list
        self.network_mock.get_resource_hash = \
            mock.Mock(return_value='fake_router_hash')

        routers_info = [{'name': 'fake_router_name_1',
                         'id': 'fake_router_id_1',
                         'admin_state_up': True,
                         'routes': [],
                         'external_gateway_info': {
                             'network_id': 'fake_network_id_1',
                             'enable_snat': True
                         },
                         'ext_net_name': 'fake_network_name_1',
                         'ext_net_tenant_name': 'fake_tenant_name_1',
                         'ext_net_id': 'fake_network_id_1',
                         'tenant_name': 'fake_tenant_name_1',
                         'ips': ['fake_ipaddr_1'],
                         'subnet_ids': ['fake_subnet_id_1'],
                         'res_hash': 'fake_router_hash',
                         'meta': {}}]

        routers_info_result = self.neutron_network_client.get_routers()
        self.assertEquals(routers_info, routers_info_result)

    def test_get_floatingips(self):

        fake_floatingips_list = {
            'floatingips': [{'router_id': None,
                             'tenant_id': 'fake_tenant_id_1',
                             'floating_network_id': 'fake_network_id_1',
                             'fixed_ip_address': None,
                             'floating_ip_address': 'fake_floatingip_1',
                             'port_id': None,
                             'id': 'fake_floating_ip_id_1'}]}

        self.neutron_mock_client().list_floatingips.return_value = \
            fake_floatingips_list
        self.neutron_mock_client.show_network.return_value = \
            {'network': {'name': 'fake_network_name_1',
                         'tenant_id': 'fake_tenant_id_1'}}

        floatingips_info = [{'id': 'fake_floating_ip_id_1',
                             'tenant_id': 'fake_tenant_id_1',
                             'floating_network_id': 'fake_network_id_1',
                             'network_name': 'fake_network_name_1',
                             'ext_net_tenant_name': 'fake_tenant_name_1',
                             'tenant_name': 'fake_tenant_name_1',
                             'fixed_ip_address': None,
                             'floating_ip_address': 'fake_floatingip_1',
                             'meta': {}}]

        floatings_info_result = self.neutron_network_client.get_floatingips()
        self.assertEquals(floatingips_info, floatings_info_result)

    def test_get_security_groups(self):

        fake_secgroups_list = {
            'security_groups': [
                {'id': 'fake_secgr_id_1',
                 'tenant_id': 'fake_tenant_id_1',
                 'name': 'fake_secgr_name_1',
                 'security_group_rules': [
                     {'remote_group_id': None,
                      'direction': 'egress',
                      'remote_ip_prefix': None,
                      'protocol': 'fake_protocol',
                      'tenant_id': 'fake_tenant_id_1',
                      'port_range_max': 22,
                      'security_group_id': 'fake_secgr_id_1',
                      'port_range_min': 22,
                      'ethertype': 'IPv4',
                      'id': 'fake_secgr_rule_id_1'}
                 ],
                 'description': 'fake_secgr_1_description'}
            ]
        }

        self.neutron_mock_client().list_security_groups.return_value = \
            fake_secgroups_list

        secgr_info = {'name': 'fake_secgr_name_1',
                      'id': 'fake_secgr_id_1',
                      'tenant_id': 'fake_tenant_id_1',
                      'tenant_name': 'fake_tenant_name_1',
                      'description': 'fake_secgr_1_description',
                      'meta': {}}

        rule_info = {'remote_group_id': None,
                     'direction': 'egress',
                     'remote_ip_prefix': None,
                     'protocol': 'fake_protocol',
                     'port_range_min': 22,
                     'port_range_max': 22,
                     'ethertype': 'IPv4',
                     'security_group_id': 'fake_secgr_id_1',
                     'meta': {}}

        rule_info['rule_hash'] = \
            self.neutron_network_client.get_resource_hash(rule_info,
                                                          'direction',
                                                          'remote_ip_prefix',
                                                          'protocol',
                                                          'port_range_min',
                                                          'port_range_max',
                                                          'ethertype')

        secgr_info['security_group_rules'] = [rule_info]
        secgr_info['res_hash'] = \
            self.neutron_network_client.get_resource_hash(secgr_info,
                                                          'name',
                                                          'tenant_name',
                                                          'description')
        secgroups_info = [secgr_info]

        self.network_mock.get_resource_hash.side_effect = [
            rule_info['rule_hash'],
            secgr_info['res_hash']
        ]

        secgr_info_result = self.neutron_network_client.get_sec_gr_and_rules()
        self.assertEquals(secgroups_info, secgr_info_result)

    def test_upload_neutron_security_groups(self):

        sg1_info = {'name': 'fake_secgr_name_1',
                    'tenant_name': 'fake_tenant_name_1',
                    'description': 'fake_secgr_1_description',
                    'res_hash': 'fake_secgr_1_hash',
                    'meta': {}}

        sg2_info = {'name': 'fake_secgr_name_2',
                    'tenant_name': 'fake_tenant_name_1',
                    'description': 'fake_secgr_2_description',
                    'res_hash': 'fake_secgr_2_hash',
                    'meta': {}}

        self.neutron_network_client.get_sec_gr_and_rules = \
            mock.Mock(return_value=[sg1_info])

        fake_secgs = [sg1_info, sg2_info]

        self.neutron_network_client.upload_neutron_security_groups(fake_secgs)

        sec_gr_info = {
            'security_group': {'name': 'fake_secgr_name_2',
                               'tenant_id': 'fake_tenant_id_1',
                               'description': 'fake_secgr_2_description'}}

        self.neutron_mock_client().create_security_group.\
            assert_called_once_with(sec_gr_info)

    def test_upload_sec_group_rules(self):

        sg1_info = {
            'name': 'fake_secgr_name_1',
            'tenant_name': 'fake_tenant_name_1',
            'description': 'fake_secgr_1_description',
            'security_group_rules': [{'remote_group_id': None,
                                      'direction': 'egress',
                                      'remote_ip_prefix': None,
                                      'protocol': 'tcp',
                                      'port_range_min': 22,
                                      'port_range_max': 22,
                                      'ethertype': 'IPv4',
                                      'security_group_id': 'fake_secgr_id_1',
                                      'rule_hash': 'fake_rule_1_hash',
                                      'meta': {}}],
            'res_hash': 'fake_secgr_1_hash'}

        sg2_info = {
            'name': 'fake_secgr_name_2',
            'tenant_name': 'fake_tenant_name_1',
            'description': 'fake_secgr_2_description',
            'security_group_rules': [{'remote_group_id': None,
                                      'direction': 'egress',
                                      'remote_ip_prefix': None,
                                      'protocol': 'tcp',
                                      'port_range_min': 80,
                                      'port_range_max': 80,
                                      'ethertype': 'IPv4',
                                      'security_group_id': 'fake_secgr_id_2',
                                      'rule_hash': 'fake_rule_2_hash',
                                      'meta': {}}],
            'res_hash': 'fake_secgr_2_hash'}

        existing_sg2_info = {
            'name': 'fake_secgr_name_2',
            'tenant_id': 'fake_existing_tenant_id',
            'tenant_name': 'fake_tenant_name_1',
            'id': 'fake_existing_secgr_id_2',
            'description': 'fake_secgr_2_description',
            'security_group_rules': [
                {'remote_group_id': None,
                 'direction': 'egress',
                 'remote_ip_prefix': None,
                 'protocol': None,
                 'port_range_min': None,
                 'port_range_max': None,
                 'ethertype': 'IPv4',
                 'security_group_id': 'fake_existing_secgr_id_2',
                 'rule_hash': 'fake_rule_2.1_hash'}
            ],
            'res_hash': 'fake_secgr_2_hash'}

        fake_existing_secgroups = [sg1_info, existing_sg2_info]

        self.neutron_network_client.get_sec_gr_and_rules = \
            mock.Mock(return_value=fake_existing_secgroups)

        self.neutron_network_client.upload_sec_group_rules([sg1_info,
                                                            sg2_info])

        rule_info = {
            'security_group_rule': {
                'direction': 'egress',
                'protocol': 'tcp',
                'port_range_min': 80,
                'port_range_max': 80,
                'ethertype': 'IPv4',
                'remote_ip_prefix': None,
                'security_group_id': 'fake_existing_secgr_id_2',
                'tenant_id': 'fake_existing_tenant_id'}
        }

        self.neutron_mock_client().create_security_group_rule.\
            assert_called_once_with(rule_info)

    def test_upload_networks(self):

        fake_existing_nets = [self.net_2_info]

        self.neutron_network_client.get_networks = \
            mock.Mock(return_value=fake_existing_nets)

        network_info = {
            'network': {'name': 'fake_network_name_1',
                        'admin_state_up': True,
                        'tenant_id': 'fake_tenant_id_1',
                        'shared': False,
                        'router:external': False,
                        'provider:physical_network': None,
                        'provider:network_type': 'gre'
                        }}

        self.neutron_network_client.upload_networks([self.net_1_info])

        if network_info['network']['provider:physical_network']:
            self.neutron_mock_client().create_network.\
                assert_called_once_with(network_info)

    def test_upload_subnets(self):

        src_net_info = copy.deepcopy(self.net_1_info)
        src_net_info['subnet_names'].append('fake_subnet_name_2')

        dst_net_info = self.net_1_info

        subnet1_info = self.subnet_1_info

        subnet2_info = copy.deepcopy(self.subnet_2_info)
        subnet2_info['network_name'] = 'fake_network_name_1'
        subnet2_info['network_id'] = 'fake_network_id_1'
        subnet2_info['tenant_name'] = 'fake_tenant_name_1'

        self.neutron_network_client.get_networks = \
            mock.Mock(return_value=[dst_net_info])
        self.neutron_network_client.get_subnets = \
            mock.Mock(return_value=[{'res_hash': 'fake_subnet_hash_1'}])

        subnet_info = {
            'subnet': {'name': 'fake_subnet_name_2',
                       'enable_dhcp': True,
                       'network_id': 'fake_network_id_1',
                       'cidr': 'fake_cidr_2',
                       'allocation_pools': [{'start': 'fake_start_ip_2',
                                             'end': 'fake_end_ip_2'}],
                       'gateway_ip': 'fake_gateway_ip_2',
                       'ip_version': 4,
                       'tenant_id': 'fake_tenant_id_1'}}

        self.neutron_network_client.upload_subnets([src_net_info],
                                                   [subnet1_info,
                                                    subnet2_info])
        self.neutron_mock_client().create_subnet.\
            assert_called_once_with(subnet_info)

    def test_upload_routers(self):

        router1_info = {
            'name': 'fake_router_name_1',
            'id': 'fake_router_id_1',
            'admin_state_up': True,
            'routes': [],
            'external_gateway_info': {'network_id': 'fake_network_id_1',
                                      'enable_snat': True},
            'ext_net_name': 'fake_network_name_1',
            'ext_net_tenant_name': 'fake_tenant_name_1',
            'ext_net_id': 'fake_network_id_1',
            'tenant_name': 'fake_tenant_name_1',
            'ips': ['fake_ipaddr_1'],
            'subnet_ids': ['fake_subnet_id_1'],
            'res_hash': 'fake_router_hash_1',
            'meta': {}}

        router2_info = {
            'name': 'fake_router_name_2',
            'id': 'fake_router_id_2',
            'admin_state_up': True,
            'routes': [],
            'external_gateway_info': {'network_id': 'fake_network_id_2',
                                      'enable_snat': True},
            'ext_net_name': 'fake_network_name_2',
            'ext_net_tenant_name': 'fake_tenant_name_2',
            'ext_net_id': 'fake_network_id_2',
            'tenant_name': 'fake_tenant_name_2',
            'ips': ['fake_ipaddr_2'],
            'subnet_ids': ['fake_subnet_id_2'],
            'res_hash': 'fake_router_hash_2',
            'meta': {}}

        src_nets_info = [self.net_1_info, self.net_2_info]
        src_subnets_info = [self.subnet_1_info, self.subnet_2_info]
        src_routers_info = [router1_info, router2_info]

        self.neutron_network_client.get_networks = \
            mock.Mock(return_value=src_nets_info)

        self.neutron_network_client.get_subnets = \
            mock.Mock(return_value=src_subnets_info)

        self.neutron_network_client.get_routers = \
            mock.Mock(return_value=[router1_info])

        self.neutron_network_client.add_router_interfaces = \
            mock.Mock(return_value=None)

        router_info = {
            'router': {'name': 'fake_router_name_2',
                       'tenant_id': 'fake_tenant_id_2',
                       'external_gateway_info': {
                           'network_id': 'fake_network_id_2'
                       }}}

        self.neutron_network_client.upload_routers(src_nets_info,
                                                   src_subnets_info,
                                                   src_routers_info)

        self.neutron_mock_client().create_router.\
            assert_called_once_with(router_info)

    def test_add_router_interfaces(self):
        src_router = {'id': 'fake_router_id_1',
                      'subnet_ids': ['fake_subnet_id_1'],
                      'external_gateway_info': None}
        src_subnets = [{'id': 'fake_subnet_id_1',
                        'external': False,
                        'res_hash': 'fake_subnet_hash'}]
        dst_router = {'id': 'fake_router_id_2',
                      'subnet_ids': ['fake_subnet_id_2'],
                      'external_gateway_info': None,
                      'name': 'r1'}
        dst_subnets = [{'id': 'fake_subnet_id_2',
                        'external': False,
                        'res_hash': 'fake_subnet_hash'}]
        self.neutron_network_client.add_router_interfaces(src_router,
                                                          dst_router,
                                                          src_subnets,
                                                          dst_subnets)

        self.neutron_mock_client().add_interface_router.\
            assert_called_once_with('fake_router_id_2',
                                    {'subnet_id': 'fake_subnet_id_2'})

    def test_hash_is_equal_for_nets_with_different_cidrs(self):
        net1 = {'cidr': "192.168.1.11/22"}
        net2 = {'cidr': "192.168.1.0/22"}
        net1_hash = neutron.NeutronNetwork.get_resource_hash(net1, 'cidr')
        net2_hash = neutron.NeutronNetwork.get_resource_hash(net2, 'cidr')
        self.assertEqual(net1_hash, net2_hash)
