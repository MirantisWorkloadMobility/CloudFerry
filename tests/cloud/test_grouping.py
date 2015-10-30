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


import os

import mock

from oslotest import mockpatch

from cloud import cloud
from cloud import grouping
from cloudferrylib.utils import utils
from tests import test


RESULT_FILE = 'tests/grouping_result'
FILE_NAME = 'tests/groups'
FAKE_CONFIG = utils.ext_dict(src=utils.ext_dict({'user': 'fake_user',
                                                 'password': 'fake_password',
                                                 'tenant': 'fake_tenant',
                                                 'host': '1.1.1.1'}),
                             migrate=utils.ext_dict(
                                 {'group_file_path': RESULT_FILE}))


class GroupingTestCase(test.TestCase):
    def setUp(self):
        super(GroupingTestCase, self).setUp()

        self.network = mock.Mock()
        self.compute = mock.Mock()
        self.identity = mock.Mock()

        self.fake_tenant1 = mock.Mock()
        self.fake_tenant1.id = 't1'
        self.fake_tenant2 = mock.Mock()
        self.fake_tenant2.id = 't2'

        self.identity.get_tenants_list.return_value = [self.fake_tenant1,
                                                       self.fake_tenant2]

        self.fake_network_1 = {'name': 'net1',
                               'id': 'net1_id',
                               'shared': False}
        self.fake_network_2 = {'name': 'net3',
                               'id': 'net3_id',
                               'shared': False}

        self.fake_subnet1 = {'network_id': 'net1_id',
                             'tenant_id': 't1',
                             'cidr': '1.1.1.0/24'}
        self.fake_subnet2 = {'network_id': 'net3_id',
                             'tenant_id': 't2',
                             'cidr': '1.1.3.0/24'}

        self.network.get_subnets_list.return_value = [self.fake_subnet1,
                                                      self.fake_subnet2]
        self.network.get_networks_list.return_value = [self.fake_network_1,
                                                       self.fake_network_2]

        self.fake_instance1 = mock.Mock()
        self.fake_instance1.id = 's1'
        self.fake_instance1.networks = {'net1': ['1.1.1.1']}
        self.fake_instance1.tenant_id = 't1'
        self.fake_instance2 = mock.Mock()
        self.fake_instance2.id = 's2'
        self.fake_instance2.networks = {'net3': ['1.1.3.1']}
        self.fake_instance2.tenant_id = 't2'
        self.fake_instance3 = mock.Mock()
        self.fake_instance3.id = 's3'
        self.fake_instance3.tenant_id = 't1'
        self.fake_instance3.networks = {'net1': ['1.1.1.2']}

        self.cloud = mock.Mock()
        self.cloud().resources = {'network': self.network,
                                  'compute': self.compute,
                                  'identity': self.identity}

        self.cloud_patch = mockpatch.PatchObject(cloud, 'Cloud',
                                                 new=self.cloud)
        self.useFixture(self.cloud_patch)

    def tearDown(self):
        super(GroupingTestCase, self).tearDown()
        os.remove(FILE_NAME)
        if utils.check_file(RESULT_FILE):
            os.remove(RESULT_FILE)

    def make_group_file(self, group_rules):
        group_file = open(FILE_NAME, 'w')
        group_file.write(group_rules)

    def test_group_by_tenant(self):
        group_rules = """
        group_by:
            - tenant
        """

        self.make_group_file(group_rules)
        group = grouping.Grouping(FAKE_CONFIG, FILE_NAME, 'src')
        group.compute.get_instances_list.return_value = [self.fake_instance1,
                                                         self.fake_instance2,
                                                         self.fake_instance3]

        group.group()

        expected_result = {'t2': ['s2'], 't1': ['s1', 's3']}

        result = utils.read_yaml_file(RESULT_FILE)
        self.assertEquals(expected_result, result)

    def test_group_by_network(self):
        group_rules = """
        group_by:
            - network
        """

        self.make_group_file(group_rules)
        group = grouping.Grouping(FAKE_CONFIG, FILE_NAME, 'src')
        group.compute.get_instances_list.return_value = [self.fake_instance1,
                                                         self.fake_instance2,
                                                         self.fake_instance3]
        group.group()

        expected_result = {'net1_id': ['s1', 's3'], 'net3_id': ['s2']}

        result = utils.read_yaml_file(RESULT_FILE)
        self.assertEquals(expected_result, result)

    def test_invalid_group(self):
        group_rules = """
        group_by:
            - some_group
        """

        self.make_group_file(group_rules)
        group = grouping.Grouping(FAKE_CONFIG, FILE_NAME, 'src')

        with self.assertRaisesRegexp(RuntimeError, 'no such grouping option'):
            group.group()
