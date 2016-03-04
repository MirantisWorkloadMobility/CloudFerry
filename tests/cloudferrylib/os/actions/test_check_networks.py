# Copyright 2015: Mirantis Inc.
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

from cloudferrylib.base import exception
from cloudferrylib.os.actions import check_networks
from tests import test


class CheckNetworksTestCase(test.TestCase):
    @staticmethod
    def get_action(src_net_info, dst_net_info=None, src_compute_info=None):
        if not dst_net_info:
            dst_net_info = {'networks': [],
                            'subnets': [],
                            'floating_ips': []}
        if not src_compute_info:
            src_compute_info = [mock.Mock(id='fake_id_1'),
                                mock.Mock(id='fake_id_2')]
        fake_src_compute = mock.Mock()
        fake_src_compute.get_instances_list.return_value = src_compute_info
        fake_src_net = mock.Mock()
        fake_src_net.read_info.return_value = src_net_info
        fake_src_net.get_ports_list.return_value = [
            {'id': 'fake_port_id',
             'network_id': 'fake_network_id',
             'device_id': 'fake_instance_id'}]

        fake_dst_net = mock.Mock()
        fake_dst_net.read_info.return_value = dst_net_info
        fake_src_cloud = mock.Mock()
        fake_dst_cloud = mock.Mock()
        fake_config = mock.MagicMock()
        fake_config.migrate.ext_net_map = None
        fake_src_cloud.resources = {'network': fake_src_net,
                                    'compute': fake_src_compute}
        fake_dst_cloud.resources = {'network': fake_dst_net}
        fake_init = {
            'src_cloud': fake_src_cloud,
            'dst_cloud': fake_dst_cloud,
            'cfg': fake_config
        }
        return check_networks.CheckNetworks(fake_init)

    def test_all_empty(self):
        src_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': []}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': []}
        self.get_action(src_net_info, dst_net_info).run()

    def test_empty_dst(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': False}],
                        'floating_ips': []}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': []}
        self.get_action(src_net_info, dst_net_info).run()

    def test_equals_networks(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': False}],
                        'floating_ips': []}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': False}],
                        'floating_ips': []}
        self.get_action(src_net_info, dst_net_info).run()

    def test_equals_and_new_networks(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {2, 5},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': False},
                                    {'cidr': '11.0.0.0/24',
                                     'res_hash': 5,
                                     'network_id': 'id1',
                                     'id': 'sub2',
                                     'external': False}],
                        'floating_ips': []}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': False}],
                        'floating_ips': []}
        self.get_action(src_net_info, dst_net_info).run()

    def test_diff(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {1},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': False
                                     }],
                        'floating_ips': []}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {3},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': False}],
                        'floating_ips': []}
        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_overlap(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/28',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': False}],
                        'floating_ips': []}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {3},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': False}],
                        'floating_ips': []}
        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_check_segmentation_id_overlapping_no_dst_networks(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'gre',
                                      'provider:segmentation_id': 200,
                                      'router:external': False}],
                        'subnets': [],
                        'floating_ips': []}

        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': []}

        self.get_action(src_net_info, dst_net_info).run()

    def test_check_segmentation_id_overlapping_same_network(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'gre',
                                      'provider:segmentation_id': 200,
                                      'router:external': False}],
                        'subnets': [],
                        'floating_ips': []}

        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'gre',
                                      'provider:segmentation_id': 200,
                                      'router:external': False}],
                        'subnets': [],
                        'floating_ips': []}

        self.get_action(src_net_info, dst_net_info).run()

    def test_check_segmentation_id_overlapping_different_network(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      "provider:physical_network": None,
                                      'provider:network_type': 'gre',
                                      'provider:segmentation_id': 200}],
                        'subnets': [],
                        'floating_ips': []}

        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 2,
                                      "provider:physical_network": None,
                                      'provider:network_type': 'gre',
                                      'provider:segmentation_id': 200}],
                        'subnets': [],
                        'floating_ips': []}

        self.get_action(src_net_info, dst_net_info)

    def test_floating_ip_overlap_clean_dst(self):
        src_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': 'test_port',
                                          'floating_network_id': 'net_id'}]}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': []}

        self.get_action(src_net_info, dst_net_info).run()

    def test_floating_ip_overlap_same_floating_ip(self):
        src_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': None,
                                          'floating_network_id': 'net_id'}]}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': None,
                                          'floating_network_id': 'net_id'}]}

        self.get_action(src_net_info, dst_net_info).run()

    def test_floating_ip_overlap_same_floating_ip_diff_parameter(self):
        src_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': None,
                                          'floating_network_id': 'net_id'}]}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'new_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': None,
                                          'floating_network_id': 'net_id'}]}

        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_floating_ip_overlap_same_floating_ip_associated_to_both_vms(self):
        src_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': 'test_port',
                                          'floating_network_id': 'net_id'}]}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': 'test_port',
                                          'floating_network_id': 'net_id'}]}

        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_floating_ip_overlap_same_floating_ip_associated_to_one_vm(self):
        src_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': None,
                                          'floating_network_id': 'net_id'}]}
        dst_net_info = {'networks': [],
                        'subnets': [],
                        'floating_ips': [{'floating_ip_address': '1.1.1.1',
                                          'tenant_name': 'test_tenant',
                                          'network_name': 'test_net',
                                          'ext_net_tenant_name': 'test_tenant',
                                          'port_id': 'test_port',
                                          'floating_network_id': 'net_id'}]}

        self.get_action(src_net_info, dst_net_info).run()

    def test_no_instance_in_external_network(self):
        src_net_info = {'networks': [{'id': 'fake_network_id',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'fake_network_id',
                                     'id': 'sub1',
                                     'external': True}],
                        'floating_ips': []}

        src_cmp_info = [mock.Mock(id='fake_instance_id_not_in_external')]

        self.get_action(src_net_info, src_compute_info=src_cmp_info).run()

    def test_instance_in_external_network(self):
        src_net_info = {'networks': [{'id': 'fake_network_id',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': False}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'fake_network_id',
                                     'id': 'sub1',
                                     'external': True}],
                        'floating_ips': []}

        src_cmp_info = [mock.Mock(id='fake_instance_id')]

        action = self.get_action(src_net_info, src_compute_info=src_cmp_info)
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_allocation_pools_overlap(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '1.1.1.1/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': True,
                                     'allocation_pools': [
                                         {'start': '1.1.1.2',
                                          'end': '1.1.1.10'},
                                         {'start': '1.1.1.20',
                                          'end': '1.1.1.30'}]
                                     }],
                        'floating_ips': []}

        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {3},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '1.1.1.1/25',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': True,
                                     'allocation_pools': [
                                         {'start': '1.1.1.5',
                                          'end': '1.1.1.15'}]
                                     }],
                        'floating_ips': []}

        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_allocation_pools_no_overlap(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {2},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '1.1.1.1/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': True,
                                     'allocation_pools': [
                                         {'start': '1.1.1.100',
                                          'end': '1.1.1.200'}]
                                     }],
                        'floating_ips': []}

        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {3},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '1.1.1.1/25',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': True,
                                     'allocation_pools': [
                                         {'start': '1.1.1.2',
                                          'end': '1.1.1.10'},
                                         {'start': '1.1.1.20',
                                          'end': '1.1.1.30'}]
                                     }],
                        'floating_ips': []}

        self.get_action(src_net_info, dst_net_info).run()

    def test_allocation_pools_same_network_and_subnet(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1,
                                      'subnets_hash': {3},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '1.1.1.1/25',
                                     'res_hash': 3,
                                     'network_id': 'id1',
                                     'id': 'sub1',
                                     'external': True,
                                     'allocation_pools': [
                                         {'start': '1.1.1.2',
                                          'end': '1.1.1.10'},
                                         {'start': '1.1.1.20',
                                          'end': '1.1.1.30'}]
                                     }],
                        'floating_ips': []}

        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1,
                                      'subnets_hash': {3},
                                      "provider:physical_network": None,
                                      'provider:network_type': 'local',
                                      'provider:segmentation_id': None,
                                      'router:external': True}],
                        'subnets': [{'cidr': '1.1.1.1/25',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2',
                                     'external': True,
                                     'allocation_pools': [
                                         {'start': '1.1.1.2',
                                          'end': '1.1.1.10'},
                                         {'start': '1.1.1.20',
                                          'end': '1.1.1.30'}]
                                     }],
                        'floating_ips': []}

        self.get_action(src_net_info, dst_net_info).run()
