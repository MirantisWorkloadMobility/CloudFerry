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
from cloudferrylib.os.actions.filter_similar_vms_from_dst import \
    FilterSimilarVMsFromDST

from tests import test


class FilterSimilarVMsFromDSTTestCase(test.TestCase):
    def test_make_tenant_ip_to_instance_id_dict(self):
        instances = {'id1': {'instance': {'id': 'id1',
                                          'tenant_id': 'tenant1',
                                          'interfaces': [
                                              {'ip_addresses': ['10.0.0.2']},
                                              {'ip_addresses': ['11.0.0.1']}]
                                          }},
                     'id2': {'instance': {'id': 'id2',
                                          'tenant_id': 'tenant1',
                                          'interfaces': [
                                              {'ip_addresses': ['10.0.0.5']}]
                                          }},
                     'id3': {'instance': {'id': 'id3',
                                          'tenant_id': 'tenant2',
                                          'interfaces': [
                                              {'ip_addresses': ['11.0.0.1']}]
                                          }},
                     'id4': {'instance': {'id': 'id4',
                                          'tenant_id': 'tenant2',
                                          'interfaces': [
                                              {'ip_addresses': ['10.0.0.2']}]
                                          }},
                     }
        result = {'tenant1': {'10.0.0.2': 'id1',
                              '11.0.0.1': 'id1',
                              '10.0.0.5': 'id2'},
                  'tenant2': {'11.0.0.1': 'id3',
                              '10.0.0.2': 'id4'}}
        self.assertEqual(result, FilterSimilarVMsFromDST.
                         make_tenant_ip_to_instance_id_dict(instances))

    def test_find_similar_instances(self):
        src_inst = {'id1': {'instance': {'id': 'id1',
                                         'tenant_id': 'tenant1',
                                         'interfaces': [
                                             {'ip_addresses': ['10.0.0.2']},
                                             {'ip_addresses': ['11.0.0.1']}],
                                         'name': 'Foo',
                                         'flav_details': 'flav1',
                                         'key_name': None,
                                         'volumes': None}},
                    'id2': {'instance': {'id': 'id2',
                                         'tenant_id': 'tenant1',
                                         'interfaces': [
                                             {'ip_addresses': ['10.0.0.5']}],
                                         'name': 'Bar',
                                         'flav_details': 'flav1',
                                         'key_name': None,
                                         'volumes': None}},
                    'id3': {'instance': {'id': 'id3',
                                         'tenant_id': 'tenant2',
                                         'interfaces': [
                                             {'ip_addresses': ['11.0.0.1']}],
                                         'name': 'Foo',
                                         'flav_details': 'flav1',
                                         'key_name': None,
                                         'volumes': None}},
                    }
        dst_inst = {'nid1': {'instance': {'id': 'nid1',
                                          'tenant_id': 'newTenant1',
                                          'interfaces': [
                                              {'ip_addresses': ['10.0.0.2']}],
                                          'name': 'Foo',
                                          'flav_details': 'flav1',
                                          'key_name': None,
                                          'volumes': None}},
                    'nid2': {'instance': {'id': 'nid2',
                                          'tenant_id': 'newTenant1',
                                          'interfaces': [
                                              {'ip_addresses': ['11.0.0.1']}],
                                          'name': 'Foo',
                                          'flav_details': 'flav1',
                                          'key_name': None,
                                          'volumes': None}},
                    'nid3': {'instance': {'id': 'nid3',
                                          'tenant_id': 'newTenant2',
                                          'interfaces': [
                                              {'ip_addresses': ['11.0.0.1']}],
                                          'name': 'Foo',
                                          'flav_details': 'flav1',
                                          'key_name': None,
                                          'volumes': None}},
                    }
        similar_inst = {'id3': {'nid3'}}
        conflict_inst = {'id1': {'nid1', 'nid2'}}
        fake_info = {'instances': dst_inst}
        fake_compute = mock.Mock()
        fake_compute.read_info.return_value = fake_info
        fake_dst_cloud = mock.Mock()
        fake_dst_cloud.resources = {'compute': fake_compute}

        fake_init = {
            'src_cloud': mock.Mock(),
            'dst_cloud': fake_dst_cloud,
            'cfg': mock.Mock()
        }
        fake_action = FilterSimilarVMsFromDST(fake_init)
        fake_action.tenant_id_to_new_id = {'tenant1': 'newTenant1',
                                           'tenant2': 'newTenant2'}
        fake_action.src_instances = src_inst
        fake_action.find_similar_instances()
        self.assertEqual(similar_inst, fake_action.similar_isntances)
        self.assertEqual(conflict_inst, fake_action.conflict_instances)
