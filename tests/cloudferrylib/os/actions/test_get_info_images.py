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

from cloudferrylib.os.actions import get_info_images
from tests import test


class GetInfoImagesTestCase(test.TestCase):
    def setUp(self):
        super(GetInfoImagesTestCase, self).setUp()

        self.fake_info = {
            'image': {'images': [{'image': 'image_body', 'meta': {}}]}}
        self.fake_image = mock.Mock()
        self.fake_image.read_info.return_value = self.fake_info
        self.fake_cloud = mock.Mock()
        self.fake_cloud.resources = {'image': self.fake_image}

    def test_run(self):
        expected_result = {'image_data': self.fake_info}

        fake_action = get_info_images.GetInfoImages(self.fake_cloud)
        image_info = fake_action.run(fake_arg='fake')

        self.assertEqual(expected_result, image_info)
        self.fake_image.read_info.assert_called_once_with(fake_arg='fake')
