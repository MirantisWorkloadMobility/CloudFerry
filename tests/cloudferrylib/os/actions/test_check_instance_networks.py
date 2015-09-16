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
import exceptions

import mock

from tests import test
from cloudferrylib.os.actions import check_instance_networks


class CheckInstanceNetworksTestCase(test.TestCase):

    @staticmethod
    def get_action(net_info, instance_ips):
        instance_info = {'instances': {
            ip: {'instance': {'name': 'name-%s' % ip,
                              'interfaces': [{'ip': ip}]}}
            for ip in instance_ips
        }}
        fake_src_net = mock.Mock()
        fake_src_net.read_info.return_value = net_info
        fake_src_compute = mock.Mock()
        fake_src_compute.read_info.return_value = instance_info
        fake_src_cloud = mock.Mock()
        fake_src_cloud.resources = {'network': fake_src_net,
                                    'compute': fake_src_compute}
        fake_init = {
            'src_cloud': fake_src_cloud,
            'cfg': {}
        }
        return check_instance_networks.CheckInstanceNetworks(fake_init,
                                                             'src_cloud')

    def test_all_empty(self):
        action = self.get_action(FakeSubnets().toMap(), [])
        action.run()

    def test_net_empty(self):
        action = self.get_action(FakeSubnets().toMap(), ['1.1.1.1', '2.2.2.2'])
        action.run()

    def test_instance_empty(self):
        action = self.get_action(FakeSubnets().add('1.1.1.1/24',True).toMap(),
                                 [])
        action.run()

    def test_good(self):
        action = self.get_action(FakeSubnets().add('10.0.0.0/24', False)
                                 .add('100.0.0.0/24', True).toMap(),
                                 ['10.0.0.1', '10.0.0.2', '10.0.0.4'])
        action.run()

    def test_negative(self):
        action = self.get_action(FakeSubnets().add('10.0.0.0/24', True)
                                 .add('100.0.0.0/24', True).toMap(),
                                 ['10.0.0.1'])
        self.assertRaisesRegex(exceptions.EnvironmentError,
                               'name-10.0.0.1',
                               action.run)

    def test_negative(self):
        action = self.get_action(FakeSubnets().add('10.0.0.0/24', True)
                                 .add('100.0.0.0/24', True).toMap(),
                                 ['10.0.0.1', '10.0.0.2', '10.0.0.4'])
        self.assertRaisesRegex(exceptions.EnvironmentError,
                               r'(?=.*\bname-10.0.0.1\b)'
                               r'(?=.*\bname-10.0.0.2\b)'
                               r'(?=.*\bname-10.0.0.4\b)',
                               action.run)


class FakeSubnets(object):
    def __init__(self):
        self.subnets = []

    def toMap(self):
        return {'subnets': self.subnets}

    def add(self, cidr, external):
        self.subnets.append({'cidr': cidr,
                             'external': external})
        return self
