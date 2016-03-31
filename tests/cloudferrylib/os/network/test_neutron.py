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

from cloudferrylib.base import exception
from cloudferrylib.os.network import neutron
from cloudferrylib.utils import utils
from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'auth_url': 'http://1.1.1.1:35357/v2.0/',
                          'region': None,
                          'service_tenant': 'services',
                          'cacert': '',
                          'insecure': False}),
    migrate=utils.ext_dict({'ext_net_map': 'fake_ext_net_map.yaml',
                            'retry': '7',
                            'time_wait': 5}),
    network=utils.ext_dict({
        'get_all_quota': True
    }))


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

        self.neutron_network_client.get_lb_pools = mock.Mock()
        self.neutron_network_client.get_lb_pools.return_value = [{
            'name': 'pool2',
            'description': 'desc2',
            'tenant_name': 'fake_tenant_name_1',
            'subnet_id': 'sub_id_2_src',
            'id': 'pool_id_2_dst',
            'protocol': 'HTTP',
            'lb_method': 'SOURCE_IP',
            'provider': 'haproxy',
            'res_hash': 'hash2'
        }]

        self.net_1_info = {'name': 'fake_network_name_1',
                           'id': 'fake_network_id_1',
                           'admin_state_up': True,
                           'shared': False,
                           'tenant_id': 'fake_tenant_id_1',
                           'tenant_name': 'fake_tenant_name_1',
                           'subnets': [mock.MagicMock()],
                           'router:external': False,
                           'provider:physical_network': None,
                           'provider:network_type': 'gre',
                           'provider:segmentation_id': 5,
                           'res_hash': 'fake_net_hash_1',
                           'subnets_hash': {'fake_subnet_hash_1'},
                           'meta': {}}

        self.net_2_info = {'name': 'fake_network_name_2',
                           'id': 'fake_network_id_2',
                           'admin_state_up': True,
                           'shared': False,
                           'tenant_id': 'fake_tenant_id_2',
                           'tenant_name': 'fake_tenant_name_2',
                           'subnet_names': ['fake_subnet_name_2'],
                           'router:external': False,
                           'provider:physical_network': 'physnet',
                           'provider:network_type': 'vlan',
                           'provider:segmentation_id': 10,
                           'res_hash': 'fake_net_hash_2',
                           'subnets_hash': {'fake_subnet_hash_2'},
                           'meta': {}}

        self.subnet_1_info = {'name': 'fake_subnet_name_1',
                              'id': 'fake_subnet_id_1',
                              'enable_dhcp': True,
                              'allocation_pools': [{'start': 'fake_start_ip_1',
                                                    'end': 'fake_end_ip_1'}],
                              'gateway_ip': 'fake_gateway_ip_1',
                              'ip_version': 4,
                              'cidr': '1.1.1.0/24',
                              'network_name': 'fake_network_name_1',
                              'external': False,
                              'network_id': 'fake_network_id_1',
                              'tenant_name': 'fake_tenant_name_1',
                              'res_hash': 'fake_subnet_hash_1',
                              'dns_nameservers': ['5.5.5.5'],
                              'meta': {}}

        self.subnet_2_info = {'name': 'fake_subnet_name_2',
                              'id': 'fake_subnet_id_2',
                              'enable_dhcp': True,
                              'allocation_pools': [{'start': 'fake_start_ip_2',
                                                    'end': 'fake_end_ip_2'}],
                              'gateway_ip': 'fake_gateway_ip_2',
                              'ip_version': 4,
                              'cidr': '2.2.2.0/25',
                              'network_name': 'fake_network_name_2',
                              'external': False,
                              'network_id': 'fake_network_id_2',
                              'tenant_name': 'fake_tenant_name_2',
                              'res_hash': 'fake_subnet_hash_2',
                              'meta': {}}

        self.segmentation_ids = {'gre': [2, 4, 6],
                                 'vlan': [3, 5, 7],
                                 'vxlan': [10, 20]}

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
            auth_url='http://1.1.1.1:35357/v2.0/',
            cacert='',
            insecure=False,
            region_name=None
        )
        self.assertEqual(self.neutron_mock_client(), client)

    def test_upload_quotas(self):
        quota = {
            'fake_tenant_name_1': {
                'subnet': 12
            }
        }
        self.neutron_network_client.upload_quota(quota)
        self.neutron_mock_client().update_quota\
            .assert_called_once_with("fake_tenant_id_1",
                                     quota['fake_tenant_name_1'])

    def test_upload_lb_monitors(self):
        self.neutron_network_client.get_lb_monitors = mock.Mock()
        self.neutron_network_client.get_lb_monitors.return_value = [
            {
                'id': 'mon_id_1_dst',
                'res_hash': 'hash_monitor_1'
            }
        ]
        monitors = [{
            'meta': {
                'id': None
            },
            'tenant_name': 'fake_tenant_name_1',
            'type': 'type1',
            'delay': '111',
            'timeout': '131',
            'max_retries': '12',
            'url_path': None,
            'res_hash': 'hash_monitor_2'
        }
        ]
        res_monitors = {
            'health_monitor': {
                'tenant_id': 'fake_tenant_id_1',
                'type': 'type1',
                'delay': '111',
                'timeout': '131',
                'max_retries': '12',
            }
        }
        self.neutron_network_client.upload_lb_monitors(monitors)
        self.neutron_mock_client().\
            create_health_monitor.assert_called_once_with(res_monitors)

    def test_upload_lb_members(self):
        self.neutron_network_client.get_subnets = mock.Mock()
        self.neutron_network_client.get_subnets.return_value = [
            {
                'id': 'sub_id_1_dst',
                'res_hash': 'hash_subnet_1'
            }
        ]
        self.neutron_network_client.get_lb_members = mock.Mock()
        self.neutron_network_client.get_lb_members.return_value = [
            {
                'id': 'member_id_1_dst',
                'res_hash': 'hash_member_2'
            }
        ]
        pools = [{
            'id': 'pool_id_src_1',
            'name': 'pool1',
            'description': 'desc1',
            'tenant_name': 'fake_tenant_name_1',
            'subnet_id': 'sub_id_1',
            'protocol': 'HTTP',
            'lb_method': 'SOURCE_IP',
            'res_hash': 'hash2',
            'meta': {
                'id': None
            }
        }]
        members = [{
            'meta': {
                'id': None
            },
            'protocol_port': '83',
            'address': '10.5.5.1',
            'pool_id': 'pool_id_src_1',
            'tenant_name': 'fake_tenant_name_1',
            'res_hash': 'hash_member_1'
        }]
        res_members = {
            'member': {
                'protocol_port': '83',
                'address': '10.5.5.1',
                'tenant_id': 'fake_tenant_id_1',
                'pool_id': 'pool_id_2_dst'
            }
        }
        self.neutron_network_client.upload_lb_members(members, pools)
        self.neutron_mock_client().\
            create_member.assert_called_once_with(res_members)

    def test_upload_lb_vips(self):
        self.neutron_network_client.get_subnets = mock.Mock()
        self.neutron_network_client.get_subnets.return_value = [
            {
                'id': 'sub_id_1_dst',
                'res_hash': 'hash_subnet_1'
            }
        ]

        pools = [{
            'id': 'pool_id_src_1',
            'name': 'pool1',
            'description': 'desc1',
            'tenant_name': 'fake_tenant_name_1',
            'subnet_id': 'sub_id_1',
            'protocol': 'HTTP',
            'lb_method': 'SOURCE_IP',
            'res_hash': 'hash2',
            'meta': {
                'id': None
            }
        }]
        vips = [
            {
                'name': 'vip1',
                'description': 'desc1',
                'address': '10.5.5.1',
                'protocol': 'HTTP',
                'protocol_port': '80',
                'connection_limit': '100',
                'pool_id': 'pool_id_src_1',
                'tenant_name': 'fake_tenant_name_1',
                'subnet_id': 'sub_id_1',
                'res_hash': 'hash1_vip',
                'session_persistence': None,
                'meta': {
                    'id': None
                }
            }
        ]
        subnets = [
            {
                'id': 'sub_id_1',
                'res_hash': 'hash_subnet_1'
            }
        ]
        res_vip = {
            'vip': {
                'name': 'vip1',
                'description': 'desc1',
                'address': '10.5.5.1',
                'protocol': 'HTTP',
                'protocol_port': '80',
                'connection_limit': '100',
                'pool_id': 'pool_id_2_dst',
                'tenant_id': 'fake_tenant_id_1',
                'subnet_id': 'sub_id_1_dst',
            }
        }
        self.neutron_network_client.upload_lb_vips(vips, pools, subnets)
        self.neutron_mock_client().\
            create_vip.assert_called_once_with(res_vip)

    def test_lb_pools(self):
        self.neutron_network_client.get_subnets = mock.Mock()
        self.neutron_network_client.get_subnets.return_value = [
            {
                'id': 'sub_id_1_dst',
                'res_hash': 'hash_subnet_1'
            }
        ]

        pools = [{
            'name': 'pool1',
            'description': 'desc1',
            'tenant_name': 'fake_tenant_name_1',
            'subnet_id': 'sub_id_1',
            'protocol': 'HTTP',
            'lb_method': 'SOURCE_IP',
            'res_hash': 'hash1',
            'meta': {
                'id': None
            }
        }]
        subnets = [
            {
                'id': 'sub_id_1',
                'res_hash': 'hash_subnet_1'
            }
        ]
        res_pools = {
            'pool': {
                'name': 'pool1',
                'description': 'desc1',
                'tenant_id': 'fake_tenant_id_1',
                'subnet_id': 'sub_id_1_dst',
                'protocol': 'HTTP',
                'lb_method': 'SOURCE_IP'
            }
        }
        self.neutron_network_client.upload_lb_pools(pools, subnets)
        self.neutron_mock_client().\
            create_pool.assert_called_once_with(res_pools)

    def test_get_quotas(self):
        ten1 = mock.Mock()
        ten1.id = "1"
        ten1.name = "ten1"
        self.identity_mock.get_tenants_list.return_value = \
            [ten1]
        self.identity_mock.try_get_tenant_name_by_id.return_value = "ten1"
        self.neutron_mock_client().show_quota.return_value = \
            {'subnet': 12}
        self.neutron_mock_client().list_quotas.return_value = {
            'quotas': [{'subnet': 12, 'tenant_id': "1"}]
        }
        expected_data = {
            'ten1': {'subnet': 12}
        }
        res1 = self.neutron_network_client.get_quota("")
        self.assertEqual(expected_data, res1)
        res2 = self.neutron_network_client.get_quota("1")
        self.assertEqual(expected_data, res2)
        FAKE_CONFIG.network.get_all_quota = False
        res3 = self.neutron_network_client.get_quota("")
        self.assertEqual(expected_data, res3)
        self.neutron_mock_client().list_quotas.return_value = {
            'quotas': [{'subnet': 12, 'tenant_id': "1"}]
        }
        res4 = self.neutron_network_client.get_quota("1")
        self.assertEqual(expected_data, res4)
        self.neutron_mock_client().list_quotas.return_value = {
            'quotas': [{'subnet': 12, 'tenant_id': "1"}]
        }
        res5 = self.neutron_network_client.get_quota("2")
        self.assertEqual(res5, {})

    def test_get_networks(self):
        fake_net_list = {'networks': [{'status': 'ACTIVE',
                                       'subnets': [mock.ANY],
                                       'name': 'fake_network_name_1',
                                       'provider:physical_network': None,
                                       'admin_state_up': True,
                                       'tenant_id': 'fake_tenant_id_1',
                                       'provider:network_type': 'gre',
                                       'router:external': False,
                                       'shared': False,
                                       'id': 'fake_network_id_1',
                                       'provider:segmentation_id': 5}]}

        fake_subnet_list = {'subnets': [{'name': 'fake_subnet_name_1',
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
                                         'cidr': '1.1.1.0/24',
                                         'dns_nameservers': ['5.5.5.5'],
                                         'id': 'fake_subnet_id_1'}]}

        self.neutron_mock_client().list_networks.return_value = fake_net_list
        self.neutron_mock_client().list_subnets.return_value = fake_subnet_list
        self.network_mock.get_networks_list = mock.Mock(
            return_value=fake_net_list['networks'])
        self.network_mock.get_resource_hash = mock.Mock(
            side_effect=['fake_subnet_hash_1', 'fake_net_hash_1'])

        networks_info = [self.net_1_info]
        networks_info_result = self.neutron_network_client.get_networks()
        networks_info_result[0]['subnets'] = [mock.ANY]
        self.assertEquals(networks_info, networks_info_result)

    def test_get_subnets(self):
        fake_net_list = {'networks': [{'status': 'ACTIVE',
                                       'subnets': [mock.ANY],
                                       'name': 'fake_network_name_1',
                                       'provider:physical_network': None,
                                       'admin_state_up': True,
                                       'tenant_id': 'fake_tenant_id_1',
                                       'provider:network_type': 'gre',
                                       'router:external': False,
                                       'shared': False,
                                       'id': 'fake_network_id_1',
                                       'provider:segmentation_id': 5}]}

        fake_subnet_list = {'subnets': [{'name': 'fake_subnet_name_1',
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
                                         'cidr': '1.1.1.0/24',
                                         'dns_nameservers': ['5.5.5.5'],
                                         'id': 'fake_subnet_id_1'}]}

        self.neutron_mock_client().list_subnets.return_value = fake_subnet_list
        self.network_mock.get_networks_list = mock.Mock(
            return_value=fake_net_list['networks'])
        self.network_mock.get_resource_hash = mock.Mock(
            return_value='fake_subnet_hash_1')

        subnets_info = [self.subnet_1_info]
        subnets_info_result = self.neutron_network_client.get_subnets()
        self.assertEquals(subnets_info, subnets_info_result)

    def test_get_routers(self):
        fake_net_list = {'networks': [{'status': 'ACTIVE',
                                       'subnets': [mock.ANY],
                                       'name': 'fake_network_name_1',
                                       'provider:physical_network': None,
                                       'admin_state_up': True,
                                       'tenant_id': 'fake_tenant_id_1',
                                       'provider:network_type': 'gre',
                                       'router:external': False,
                                       'shared': False,
                                       'id': 'fake_network_id_1',
                                       'provider:segmentation_id': 5}]}

        fake_router_list = {'routers': [{'status': 'ACTIVE',
                                         'external_gateway_info': {
                                             'network_id': 'fake_network_id_1',
                                             'enable_snat': True
                                         },
                                         'name': 'fake_router_name_1',
                                         'admin_state_up': True,
                                         'tenant_id': 'fake_tenant_id_1',
                                         'routes': [],
                                         'id': 'fake_router_id_1'}]}

        fake_ports_list = [{'fixed_ips': [{'subnet_id': 'fake_subnet_id_1',
                                           'ip_address': 'fake_ipaddr_1'}],
                            'device_id': 'fake_router_id_1'}]

        self.neutron_mock_client().list_routers.return_value = fake_router_list
        self.network_mock.get_networks_list = mock.Mock(
            return_value=fake_net_list['networks'])
        self.network_mock.get_ports_list.return_value = fake_ports_list
        self.network_mock.get_resource_hash = mock.Mock(
            return_value='fake_router_hash')
        self.network_mock.get_ports_info.return_value = \
            {'subnet_ids': {'fake_subnet_id_1', }, 'ips': {'fake_ipaddr_1', }}

        routers_info = [{'name': 'fake_router_name_1',
                         'id': 'fake_router_id_1',
                         'admin_state_up': True,
                         'external_gateway_info': {
                             'network_id': 'fake_network_id_1',
                             'enable_snat': True
                         },
                         'ext_net_name': 'fake_network_name_1',
                         'ext_net_tenant_name': 'fake_tenant_name_1',
                         'ext_net_id': 'fake_network_id_1',
                         'tenant_name': 'fake_tenant_name_1',
                         'ips': {'fake_ipaddr_1', },
                         'subnet_ids': {'fake_subnet_id_1', },
                         'res_hash': 'fake_router_hash',
                         'meta': {}}]

        routers_info_result = self.neutron_network_client.get_routers()
        self.assertEqual(routers_info, routers_info_result)

    def test_get_floatingips(self):
        fake_net_list = {'networks': [{'status': 'ACTIVE',
                                       'subnets': [mock.ANY],
                                       'name': 'fake_network_name_1',
                                       'provider:physical_network': None,
                                       'admin_state_up': True,
                                       'tenant_id': 'fake_tenant_id_1',
                                       'provider:network_type': 'gre',
                                       'router:external': False,
                                       'shared': False,
                                       'id': 'fake_network_id_1',
                                       'provider:segmentation_id': 5}]}

        fake_fips = {'floatingips': [
            {'router_id': None,
             'tenant_id': 'fake_tenant_id_1',
             'floating_network_id': 'fake_network_id_1',
             'fixed_ip_address': None,
             'floating_ip_address': 'fake_floatingip_1',
             'port_id': None,
             'id': 'fake_floating_ip_id_1'}]}

        self.network_mock.get_networks_list = mock.Mock(
            return_value=fake_net_list['networks'])
        self.neutron_mock_client().list_floatingips.return_value = fake_fips

        floatingips_info = [{'id': 'fake_floating_ip_id_1',
                             'tenant_id': 'fake_tenant_id_1',
                             'floating_network_id': 'fake_network_id_1',
                             'network_name': 'fake_network_name_1',
                             'ext_net_tenant_name': 'fake_tenant_name_1',
                             'tenant_name': 'fake_tenant_name_1',
                             'fixed_ip_address': None,
                             'floating_ip_address': 'fake_floatingip_1',
                             'port_id': None,
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

        self.neutron_network_client.upload_networks([self.net_1_info],
                                                    self.segmentation_ids, [])

        if network_info['network']['provider:physical_network']:
            self.neutron_mock_client().create_network.\
                assert_called_once_with(network_info)

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
            'ips': {'fake_ipaddr_1', },
            'subnet_ids': {'fake_subnet_id_1', },
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
            'ips': {'fake_ipaddr_2', },
            'subnet_ids': {'fake_subnet_id_2', },
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

        self.neutron_network_client.convert_routers = \
            mock.Mock(return_value=router2_info)

        router_info = {
            'router': {'name': 'fake_router_name_2',
                       'tenant_id': 'fake_tenant_id_2',
                       }}

        self.neutron_network_client.upload_routers(src_nets_info,
                                                   src_subnets_info,
                                                   src_routers_info)

        self.neutron_mock_client().create_router.\
            assert_called_once_with(router_info)

    def test_add_router_interfaces(self):
        src_router = {'id': 'fake_router_id_1',
                      'subnet_ids': {'fake_subnet_id_1', },
                      'external_gateway_info': None,
                      'name': 'r1'}
        src_subnets = [{'id': 'fake_subnet_id_1',
                        'external': False,
                        'res_hash': 'fake_subnet_hash'}]
        dst_router = {'id': 'fake_router_id_2',
                      'subnet_ids': set(),
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

    def test_get_network_from_list_by_id(self):
        networks_list = [self.net_1_info, self.net_2_info]

        network = neutron.get_network_from_list_by_id('fake_network_id_2',
                                                      networks_list)
        self.assertEqual(self.net_2_info, network)

    def test_get_network_from_list(self):
        subnet1 = copy.deepcopy(self.subnet_1_info)
        subnet2 = copy.deepcopy(self.subnet_2_info)
        subnet1['tenant_id'] = 'fake_tenant_id_1'
        subnet2['tenant_id'] = 'fake_tenant_id_2'
        subnet2['cidr'] = '192.168.1.0/24'

        subnets_list = [subnet1, subnet2]
        networks_list = [self.net_1_info, self.net_2_info]

        network = neutron.get_network_from_list(ip='192.168.1.13',
                                                tenant_id='fake_tenant_id_2',
                                                networks_list=networks_list,
                                                subnets_list=subnets_list)

        self.assertEqual(self.net_2_info, network)

    def test_get_segmentation_ids_from_net_list(self):
        networks_list = [self.net_1_info, self.net_2_info]
        seg_ids = {'gre': [5],
                   'vlan': [10]}

        result = neutron.get_segmentation_ids_from_net_list(networks_list)

        self.assertEqual(seg_ids, result)

    def test_generate_new_segmentation_id(self):
        dst_seg_ids = {'gre': [2, 4, 6, 14, 21],
                       'vlan': [3, 5, 7, 10, 12],
                       'vxlan': [10, 30, 40]}

        seg_id = neutron.generate_new_segmentation_id(self.segmentation_ids,
                                                      dst_seg_ids,
                                                      'gre')

        self.assertEqual(3, seg_id)

    def test_generate_new_segmentation_id_vlan_limit(self):
        dst_seg_ids = {'gre': [2, 4, 6, 14, 21],
                       'vlan': range(2, 4096),
                       'vxlan': [10, 30, 40]}

        self.assertRaises(exception.AbortMigrationError,
                          neutron.generate_new_segmentation_id,
                          self.segmentation_ids,
                          dst_seg_ids,
                          'vlan')


class NeutronRouterTestCase(test.TestCase):
    def test_router_class(self):
        router_info = {'id': 'routerID',
                       'tenant_name': 'Tenant1',
                       'ext_net_id': 'ext_network',
                       'subnet_ids': ['sub1', 'sub2'],
                       'ips': ['10.0.0.2', '123.0.0.15']}
        subnets = {'sub1': {'network_id': 'ext_network',
                            'cidr': '123.0.0.0/24'},
                   'sub2': {'network_id': 'int_network',
                            'cidr': '10.0.0.0/24'}}
        router = neutron.Router(router_info, subnets)
        self.assertEqual('routerID', router.id)
        self.assertEqual('ext_network', router.ext_net_id)
        self.assertEqual(['10.0.0.0/24'], router.int_cidr)
        self.assertEqual('123.0.0.0/24', router.ext_cidr)
        self.assertEqual('sub1', router.ext_subnet_id)
        self.assertEqual('Tenant1', router.tenant_name)
        self.assertEqual('123.0.0.15', router.ext_ip)


@mock.patch("cloudferrylib.os.network.neutron.neutron_client.Client")
@mock.patch("cloudferrylib.os.network.neutron.utl.read_yaml_file",
            mock.MagicMock())
class NeutronClientTestCase(test.TestCase):
    def test_adds_region_if_set_in_config(self, n_client):
        cloud = mock.MagicMock()
        config = mock.MagicMock()

        tenant = 'tenant'
        region = 'region'
        user = 'user'
        auth_url = 'auth_url'
        password = 'password'
        insecure = False
        cacert = ''

        config.cloud.user = user
        config.cloud.tenant = tenant
        config.cloud.region = region
        config.cloud.auth_url = auth_url
        config.cloud.password = password
        config.cloud.insecure = insecure
        config.cloud.cacert = cacert

        n = neutron.NeutronNetwork(config, cloud)
        n.get_client()

        n_client.assert_called_with(
            region_name=region,
            tenant_name=tenant,
            password=password,
            auth_url=auth_url,
            username=user,
            cacert=cacert,
            insecure=insecure
        )

    def test_does_not_add_region_if_not_set_in_config(self, n_client):
        cloud = mock.MagicMock()
        config = mock.MagicMock()

        tenant = 'tenant'
        user = 'user'
        auth_url = 'auth_url'
        password = 'password'
        insecure = False
        cacert = ''

        config.cloud.region = None
        config.cloud.user = user
        config.cloud.tenant = tenant
        config.cloud.auth_url = auth_url
        config.cloud.password = password
        config.cloud.insecure = insecure
        config.cloud.cacert = cacert

        n = neutron.NeutronNetwork(config, cloud)
        n.get_client()

        n_client.assert_called_with(
            tenant_name=tenant,
            password=password,
            auth_url=auth_url,
            username=user,
            cacert=cacert,
            insecure=insecure,
            region_name=None
        )
