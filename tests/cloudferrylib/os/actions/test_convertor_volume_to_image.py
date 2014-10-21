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

from cloudferrylib.os.actions import converter_volume_to_image
from tests import test


class ConverterVolumeToImageTest(test.TestCase):
    def setUp(self):
        super(ConverterVolumeToImageTest, self).setUp()
        self.fake_cloud = mock.Mock()
        self.fake_storage = mock.Mock()
        self.fake_storage.deploy = mock.Mock()
        self.fake_storage.upload_volume_to_image.return_value = (
            'resp', 'image_id')
        self.fake_storage.get_backend.return_value = 'ceph'
        self.fake_image = mock.Mock()
        self.fake_image.wait_for_status = mock.Mock()
        self.fake_image.read_info = mock.Mock()
        self.fake_image.read_info.return_value = {
            'image': {'images': [{'image': 'image_body', 'meta': {}}]}}
        self.fake_image.patch_image = mock.Mock()
        self.fake_cloud.resources = {'storage': self.fake_storage,
                                     'image': self.fake_image}
        self.fake_volumes_info = {
            'storage': {
                'volumes': [{
                    'volume': {
                        'id': 'id1',
                        'display_name': 'dis1',

                    },
                    'meta': {
                        'image': 'image'
                    }
                }]
            }
        }

    def test_action(self):
        fake_action = converter_volume_to_image.ConverterVolumeToImage(
            "QCOW2",
            self.fake_cloud)
        res = fake_action.run(self.fake_volumes_info)
        self.assertEqual('image_body',
                         res['images_info']['image']['images'][0]['image'])
        self.assertEqual('dis1',
                         res['images_info']['image']['images'][0]['meta'][
                             'volume']['display_name'])
