# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.
import mock
from cloudferrylib.os.image.GlanceImage import GlanceImage
from oslotest import mockpatch
from glanceclient.v1 import client as glance_client
from tests import test


__author__ = 'asvechnikov'

FAKE_CONFIG = {}


class GlanceImageTestCase(test.TestCase):
    def setUp(self):
        super(GlanceImageTestCase, self).setUp()

        self.glance_mock_client = mock.MagicMock()

        self.glance_client_patch = mockpatch.PatchObject(glance_client, 'Client',
                                                         new=self.glance_mock_client)
        self.useFixture(self.glance_client_patch)
        self.identity_mock = mock.Mock()

        self.glance_image = GlanceImage(FAKE_CONFIG, self.identity_mock)

        self.fake_image_1 = mock.Mock()
        self.fake_image_1.id = 'fake_image_id_1'
        self.fake_image_1.status = 'fake_status_1'
        self.fake_image_1._resp = 'fake_resp_1'
        self.fake_image_1.checksum = 'fake_shecksum_1'

        self.fake_image_2 = mock.Mock()

    def test_get_client(self):
        fake_endpoint = 'fake_endpoint'
        fake_auth_token = 'fake_auth_token'
        self.identity_mock.get_endpoint_by_name_service.return_value = fake_endpoint
        self.identity_mock.get_auth_token_from_user.return_value = fake_auth_token

        glance_client = self.glance_image.get_glance_client()
        mock_calls = [mock.call(endpoint=fake_endpoint, token=fake_auth_token)]

        self.glance_mock_client.assert_has_calls(mock_calls)
        self.assertEqual(self.glance_mock_client(), glance_client)

    def test_get_images_list(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(fake_images, self.glance_image.get_image_list())

    def test_create_image(self):
        self.glance_image.create_image(name='fake_image_name', data='fake_data')
        test_args = {'name': 'fake_image_name',
                     'data': 'fake_data'}

        self.glance_mock_client().images.create.assert_called_once_with(**test_args)

    def test_delete_image(self):
        fake_image_id = 'fake_image_id_1'
        self.glance_image.delete_image(fake_image_id)

        self.glance_mock_client().images.delete.assert_called_once_with(fake_image_id)

    def test_get_image(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1, self.glance_image.get_image('fake_image_id_1'))

    def test_get_image_status(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1.status, self.glance_image.get_image_status('fake_image_id_1'))

    def test_get_ref_image(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1._resp, self.glance_image.get_ref_image('fake_image_id_1'))

    def test_get_image_checksum(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1.checksum, self.glance_image.get_image_checksum('fake_image_id_1'))