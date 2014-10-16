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

from cloudferrylib.os.actions import convertor_image_to_volume
from tests import test


class ConvertorImageToVolumeTest(test.TestCase):
    def setUp(self):
        super(ConvertorImageToVolumeTest, self).setUp()
        self.fake_cloud = mock.Mock()
        self.fake_storage = mock.Mock()
        self.fake_storage.deploy = mock.Mock()
        vol1 = mock.Mock(id="id1")
        self.fake_storage.deploy.return_value = [vol1]
        volume = 'volume_body_dst'
        self.fake_storage.read_info.return_value = {'storage': {'volumes': [{'volume': volume, 'meta': {}}]}}
        self.fake_image = mock.Mock()
        self.fake_cloud.resources = {'storage': self.fake_storage,
                                     'image': self.fake_image}

    def test_action(self):
        action = convertor_image_to_volume.ConvertorImageToVolume()
        images_fake = dict(image=dict(images=[{
            'image': 'image_body',
            'meta': {
                'volume': 'volume_body'
            }
        }]))
        res = action.run(images_fake, self.fake_cloud)
        self.assertEqual('volume_body_dst', res['volumes_info']['storage']['volumes'][0]['volume'])
        self.assertEqual('image_body', res['volumes_info']['storage']['volumes'][0]['meta']['image'])


