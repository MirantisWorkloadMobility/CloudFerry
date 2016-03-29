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


import mock

from cloudferry.lib.os.actions import convert_image_to_volume
from tests import test


class ConverterImageToVolumeTest(test.TestCase):
    def setUp(self):
        super(ConverterImageToVolumeTest, self).setUp()
        self.fake_src_cloud = mock.Mock()

        self.fake_volume = {
            'volume': {
                'size': 'size1',
                'display_name': 'display_name1',
                'display_description': 'display_description1',
                'volume_type': 'volume_type1',
                'availability_zone': 'availability_zone1'},
            'meta': {'image': {'id': 'image_id1'}}}

        self.fake_vol_info = {'volumes': {'id1': self.fake_volume}}

        self.fake_storage = mock.Mock()
        self.fake_storage.deploy = mock.Mock()
        self.fake_storage.deploy.return_value = self.fake_vol_info['volumes']

        self.fake_storage.read_info.return_value = self.fake_vol_info
        self.fake_image = mock.Mock()
        self.fake_src_cloud.resources = {'storage': self.fake_storage,
                                         'image': self.fake_image}

        self.fake_dst_cloud = mock.Mock()

        self.fake_config = {}

        self.fake_init = {
            'src_cloud': self.fake_src_cloud,
            'dst_cloud': self.fake_dst_cloud,
            'cfg': self.fake_config
        }

        self.fake_result_info = {
            'images': {
                'fake_image_id_1': {'image': {'checksum': 'fake_shecksum_1',
                                              'container_format': 'bare',
                                              'disk_format': 'qcow2',
                                              'id': 'fake_image_id_1',
                                              'is_public': True,
                                              'name': 'fake_image_name_1',
                                              'protected': False,
                                              'size': 1024,
                                              'properties': 'fake_properties'},
                                    'meta': {
                                        'volume': {
                                            'id': 'fake_vol_id'
                                        },
                                        'instance': {}}
                                    }},
        }

    def test_action(self):
        action = convert_image_to_volume.ConvertImageToVolume(
            self.fake_init,
            cloud='src_cloud')

        res = action.run(self.fake_result_info)

        exp_volume = {'availability_zone': 'availability_zone1',
                      'display_description': 'display_description1',
                      'display_name': 'display_name1',
                      'size': 'size1',
                      'volume_type': 'volume_type1'}

        self.assertEqual(
            exp_volume,
            res['storage_info']['volumes']['id1']['volume'])

        exp_image = {'checksum': 'fake_shecksum_1',
                     'container_format': 'bare',
                     'disk_format': 'qcow2',
                     'id': 'fake_image_id_1',
                     'is_public': True,
                     'name': 'fake_image_name_1',
                     'properties': 'fake_properties',
                     'protected': False,
                     'size': 1024}

        self.assertEqual(
            exp_image,
            res['storage_info']['volumes']['id1']['meta']['image'])
