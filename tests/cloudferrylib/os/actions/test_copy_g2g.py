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

from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.utils import utils
from tests import test


class CopyFromGlanceToGlanceTestCase(test.TestCase):
    def setUp(self):
        super(CopyFromGlanceToGlanceTestCase, self).setUp()

        self.fake_input_info = {'image_data': {'fake_key': 'fake_value'}}
        self.fake_result_info = {'image_data': {
            'image': {'images': [{'image': 'image_body', 'meta': {}}]}}}

        self.fake_image = mock.Mock()
        self.fake_image.deploy.return_value = self.fake_result_info
        self.src_cloud = mock.Mock()
        self.dst_cloud = mock.Mock()
        self.dst_cloud.resources = {'image': self.fake_image}

        self.fake_config = utils.ext_dict(migrate=utils.ext_dict(
            {'ignore_empty_images': False}))
        self.src_cloud.resources = {'image': self.fake_image}

        self.fake_init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.fake_config
        }

    def test_run_with_info(self):
        fake_action = copy_g2g.CopyFromGlanceToGlance(self.fake_init)

        new_info = fake_action.run(image_info=self.fake_input_info)

        self.assertEqual({'images_info': self.fake_result_info}, new_info)

        self.fake_image.deploy.assert_called_once_with(
            {'images_info': self.fake_image.read_info()})

    @mock.patch('cloudferrylib.os.actions.get_info_images.GetInfoImages')
    def test_run_no_info(self, mock_info):
        mock_info().run.return_value = self.fake_input_info

        fake_action = copy_g2g.CopyFromGlanceToGlance(self.fake_init)
        new_info = fake_action.run()

        self.assertEqual({'images_info': self.fake_result_info}, new_info)
        self.fake_image.deploy.assert_called_once_with(
            {'image_data': {'fake_key': 'fake_value'}})
