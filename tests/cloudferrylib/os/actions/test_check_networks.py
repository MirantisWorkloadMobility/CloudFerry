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
import exceptions

from tests import test
from cloudferrylib.os.actions import check_networks


class CheckNetworksTestCase(test.TestCase):

    def setUp(self):
        super(CheckNetworksTestCase, self).setUp()

    @staticmethod
    def get_action(src_net_info, dst_net_info):
        fake_src_net = mock.Mock()
        fake_src_net.read_info.return_value = src_net_info
        fake_dst_net = mock.Mock()
        fake_dst_net.read_info.return_value = dst_net_info
        fake_src_cloud = mock.Mock()
        fake_dst_cloud = mock.Mock()
        fake_config = {}
        fake_src_cloud.resources = {'network': fake_src_net}
        fake_dst_cloud.resources = {'network': fake_dst_net}
        fake_init = {
            'src_cloud': fake_src_cloud,
            'dst_cloud': fake_dst_cloud,
            'cfg': fake_config
        }
        return check_networks.CheckNetworks(fake_init)

    def test_all_empty(self):
        src_net_info = {'networks': [],
                        'subnets': []}
        dst_net_info = {'networks': [],
                        'subnets': []}
        self.get_action(src_net_info, dst_net_info).run()

    def test_empty_dst(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1'}]}
        dst_net_info = {'networks': [],
                        'subnets': []}
        self.get_action(src_net_info, dst_net_info).run()

    def test_equals_networks(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1'}]}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id2',
                                     'id': 'sub2'}]}
        self.get_action(src_net_info, dst_net_info).run()

    def test_equals_and_new_networks(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1'},
                                    {'cidr': '11.0.0.0/24',
                                     'res_hash': 5,
                                     'network_id': 'id1',
                                     'id': 'sub2'}]}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id2',
                                     'id': 'sub2'}]}
        self.get_action(src_net_info, dst_net_info).run()

    def test_diff(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1'}]}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2'}]}
        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exceptions.EnvironmentError, action.run)

    def test_overlap(self):
        src_net_info = {'networks': [{'id': 'id1',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/28',
                                     'res_hash': 2,
                                     'network_id': 'id1',
                                     'id': 'sub1'}]}
        dst_net_info = {'networks': [{'id': 'id2',
                                      'res_hash': 1}],
                        'subnets': [{'cidr': '10.0.0.0/24',
                                     'res_hash': 3,
                                     'network_id': 'id2',
                                     'id': 'sub2'}]}
        action = self.get_action(src_net_info, dst_net_info)
        self.assertRaises(exceptions.EnvironmentError, action.run)
