# Copyright (c) 2015 Mirantis Inc.
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

from tests import test
from cloudferrylib.base import exception
from cloudferrylib.os.actions import verify_vms


class VerifyVmsTest(test.TestCase):
    def setUp(self):
        super(VerifyVmsTest, self).setUp()
        self.fake_src_cloud = mock.Mock()

        self.fake_info = {
            'instances': {
                'id1': {
                    'instance': {
                        'name': 'fake_inst_name_1',
                        'flav_details': {
                            'cpus': 1
                        },
                        'interfaces': {
                            'int': 'int1'
                        },
                        'key_name': 'fake_key_name_1',
                        'volumes': [{
                            'dev': 1
                        }],
                        'server_group': 'fake_server_group_1',
                    }
                },
                'id2': {
                    'instance': {
                        'name': 'fake_inst_name_2',
                        'flav_details': {
                            'cpus': 1
                        },
                        'interfaces': {
                            'int': 'int2'
                        },
                        'key_name': 'fake_key_name_2',
                        'volumes': [{
                            'dev': 1
                        }],
                        'server_group': 'fake_server_group_2',
                    }
                }
            }
        }

        self.fake_compute = mock.Mock()
        self.fake_src_cloud.resources = {
            'compute': self.fake_compute
        }

        self.fake_init = {
            'src_cloud': self.fake_src_cloud,
        }

        self.fake_dst_info = {
            'instances': {
                'new_id1': {
                    'instance': {
                        'name': 'fake_inst_name_1',
                        'flav_details': {
                            'cpus': 1
                        },
                        'key_name': 'fake_key_name_1',
                        'interfaces': {
                            'int': 'int1'
                        },
                        'server_group': 'fake_server_group_1',
                    },
                    'meta': {
                        'old_id': 'id1',
                        'volume': [{
                            'volume': {
                                'dev': 1
                            }
                        }]
                    }
                },
                'new_id2': {
                    'instance': {
                        'name': 'fake_inst_name_2',
                        'flav_details': {
                            'cpus': 1
                        },
                        'key_name': 'fake_key_name_2',
                        'interfaces': {
                            'int': 'int2'
                        },
                        'server_group': 'fake_server_group_2',
                    },
                    'meta': {
                        'old_id': 'id2',
                        'volume': [{
                            'volume': {
                                'dev': 1
                            }
                        }]
                    }
                }
            }
        }

    def test_verify_vms_no_exc(self):
        action = verify_vms.VerifyVms(
            self.fake_init,
            cloud='src_cloud')
        try:
            action.run(info=self.fake_dst_info, info_backup=self.fake_info)
        except exception.AbortMigrationError as e:
            self.fail(e)

    def test_verify_vms_exc(self):
        action = verify_vms.VerifyVms(
            self.fake_init,
            cloud='src_cloud')
        self.assertRaises(exception.AbortMigrationError, action.run)

    def test_verify_vms_all(self):
        action = verify_vms.VerifyVms(
            self.fake_init,
            cloud='src_cloud')
        res = action.run(info=self.fake_dst_info, info_backup=self.fake_info)
        self.assertEqual(True, res)
