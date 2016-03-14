# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from glanceclient import exc as glance_exc
import mock
from tests import test

from cloudferrylib.base import exception
from cloudferrylib.os.actions import check_filter


class CheckFilterTestCase(test.TestCase):
    def setUp(self):
        super(CheckFilterTestCase, self).setUp()

        fake_src_cloud = mock.Mock()
        self.fake_src_image = mock.Mock()

        fake_src_cloud.resources = {
            'image': self.fake_src_image,
        }

        self.fake_init = {
            'src_cloud': fake_src_cloud,
        }

    def test_check_opts_img_with_error_in_filter_config(self):
        fake_action = check_filter.CheckFilter(self.fake_init,
                                               cloud='src_cloud')

        opts = {
            'images_list': 'foo',
            'exclude_images_list': 'bar',
        }

        self.assertRaises(exception.AbortMigrationError,
                          fake_action._check_opts_img,
                          opts)

    def test_check_opts_img_if_image_exists(self):
        fake_action = check_filter.CheckFilter(self.fake_init,
                                               cloud='src_cloud')
        image = mock.Mock()

        opts = {
            'images_list': [image.id]
        }
        self.fake_src_image.glance_client.images.get.return_value = image

        fake_action._check_opts_img(opts)

        self.fake_src_image.glance_client.images.\
            get.assert_called_once_with(image.id)

    def test_check_opts_img_if_doesnt_image_exist(self):
        fake_action = check_filter.CheckFilter(self.fake_init,
                                               cloud='src_cloud')
        image = mock.Mock()
        opts = {
            'images_list': [image.id]
        }
        self.fake_src_image.glance_client.images.\
            get.side_effect = glance_exc.HTTPNotFound

        self.assertRaises(glance_exc.HTTPNotFound,
                          fake_action._check_opts_img,
                          opts)

        self.fake_src_image.glance_client.images.\
            get.assert_called_once_with(image.id)
