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

import copy
import mock

from glanceclient.v1 import client as glance_client
from oslotest import mockpatch

from cloudferrylib.os.image.glance_image import GlanceImage
from cloudferrylib.utils import file_like_proxy
from cloudferrylib.utils import utils
from tests import test


FAKE_CONFIG = utils.ext_dict(cloud=utils.ext_dict({'user': 'fake_user',
                                                   'password': 'fake_password',
                                                   'tenant': 'fake_tenant',
                                                   'host': '1.1.1.1',
                                                   }),
                             migrate=utils.ext_dict({'speed_limit': '10MB'}))


class GlanceImageTestCase(test.TestCase):
    def setUp(self):
        super(GlanceImageTestCase, self).setUp()

        self.glance_mock_client = mock.MagicMock()
        self.glance_mock_client().images.data()._resp = 'fake_resp_1'

        self.glance_client_patch = mockpatch.PatchObject(
            glance_client,
            'Client',
            new=self.glance_mock_client)
        self.useFixture(self.glance_client_patch)
        self.identity_mock = mock.Mock()

        self.fake_cloud = mock.Mock()
        self.fake_cloud.mysql_connector = mock.Mock()

        self.fake_cloud.resources = dict(identity=self.identity_mock)
        self.glance_image = GlanceImage(FAKE_CONFIG, self.fake_cloud)

        self.fake_image_1 = mock.Mock()
        self.fake_image_1.id = 'fake_image_id_1'
        self.fake_image_1.name = 'fake_image_name_1'
        self.fake_image_1.status = 'fake_status_1'
        self.fake_image_1.checksum = 'fake_shecksum_1'
        self.fake_image_1.container_format = 'bare'
        self.fake_image_1.disk_format = 'qcow2'
        self.fake_image_1.is_public = True
        self.fake_image_1.protected = False
        self.fake_image_1.size = 1024

        self.fake_image_2 = mock.Mock()
        self.fake_image_2.name = 'fake_image_name_2'

        self.fake_input_info = {'image': {'resource': self.glance_image,
                                          'images': {}}
                                }

        self.fake_result_info = {'image': {
            'images': {
                'fake_image_id_1': {'image': {'checksum': 'fake_shecksum_1',
                                              'container_format': 'bare',
                                              'disk_format': 'qcow2',
                                              'id': 'fake_image_id_1',
                                              'is_public': True,
                                              'name': 'fake_image_name_1',
                                              'protected': False,
                                              'size': 1024},
                                    'meta': {}}},
            'resource': self.glance_image}}

    def test_get_glance_client(self):
        fake_endpoint = 'fake_endpoint'
        fake_auth_token = 'fake_auth_token'
        self.identity_mock.get_endpoint_by_service_name.return_value = (
            fake_endpoint)
        self.identity_mock.get_auth_token_from_user.return_value = (
            fake_auth_token)

        gl_client = self.glance_image.get_glance_client()
        mock_calls = [mock.call(endpoint=fake_endpoint, token=fake_auth_token)]

        self.glance_mock_client.assert_has_calls(mock_calls)
        self.assertEqual(self.glance_mock_client(), gl_client)

    def test_get_image_list(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(fake_images, self.glance_image.get_image_list())

    def test_create_image(self):
        self.glance_image.create_image(name='fake_image_name',
                                       data='fake_data')
        test_args = {'name': 'fake_image_name',
                     'data': 'fake_data'}

        self.glance_mock_client().images.create.assert_called_once_with(
            **test_args)

    def test_delete_image(self):
        fake_image_id = 'fake_image_id_1'
        self.glance_image.delete_image(fake_image_id)

        self.glance_mock_client().images.delete.assert_called_once_with(
            fake_image_id)

    def test_get_image_by_id(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1,
                          self.glance_image.get_image_by_id('fake_image_id_1'))

    def test_get_image_by_name(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(
            self.fake_image_1,
            self.glance_image.get_image_by_name('fake_image_name_1'))

    def test_get_image(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1,
                          self.glance_image.get_image('fake_image_id_1'))

        self.assertEquals(self.fake_image_2,
                          self.glance_image.get_image('fake_image_name_2'))

    def test_get_image_status(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1.status,
                          self.glance_image.get_image_status(
                              'fake_image_id_1'))

    def test_get_ref_image(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals('fake_resp_1',
                          self.glance_image.get_ref_image('fake_image_id_1'))

    def test_get_image_checksum(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        self.assertEquals(self.fake_image_1.checksum,
                          self.glance_image.get_image_checksum(
                              'fake_image_id_1'))

    def test_make_image_info(self):
        info = self.glance_image.make_image_info(self.fake_image_1,
                                                 self.fake_input_info)

        self.assertEqual(self.fake_result_info, info)

    def test_make_image_info_no_image(self):
        info = self.glance_image.make_image_info(self.fake_image_1,
                                                 self.fake_input_info)

        self.assertEqual(self.fake_input_info, info)

    def test_read_info_id(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        info = self.glance_image.read_info(image_id='fake_image_id_1')
        self.assertEqual(self.fake_result_info, info)

    def test_read_info_name(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        info = self.glance_image.read_info(image_name='fake_image_name_1')
        self.assertEqual(self.fake_result_info, info)

    def test_read_info_list(self):
        fake_images = [self.fake_image_1, self.fake_image_2]
        self.glance_mock_client().images.list.return_value = fake_images

        info = self.glance_image.read_info(images_list=['fake_image_name_1'])
        self.assertEqual(self.fake_result_info, info)

    def test_read_info_default(self):
        fake_images = [self.fake_image_1]
        self.glance_mock_client().images.list.return_value = fake_images

        info = self.glance_image.read_info()
        self.assertEqual(self.fake_result_info, info)

    @mock.patch('cloudferrylib.utils.file_like_proxy.FileLikeProxy')
    def test_deploy(self, mock_proxy):
        info = copy.deepcopy(self.fake_result_info)
        self.glance_mock_client().images.create.return_value = (
            self.fake_image_1)

        fake_images1 = [self.fake_image_2, mock.Mock()]
        fake_images2 = [self.fake_image_1, self.fake_image_2]

        self.glance_mock_client().images.list.side_effect = (fake_images1,
                                                             fake_images2)

        new_info = self.glance_image.deploy(info)

        self.assertEqual(self.fake_result_info, new_info)
        mock_proxy.assert_called_once_with(
            info['image']['images']['fake_image_id_1']['image'],
            file_like_proxy.callback_print_progress,
            '10MB')
