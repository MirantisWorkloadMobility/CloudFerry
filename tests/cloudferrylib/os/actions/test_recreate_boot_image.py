# Copyright (c) 2016 Mirantis Inc.
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

from cloudferrylib.os.actions import recreate_boot_image
from cloudferrylib.utils import utils

from tests import test


class ReCreateBootImageTestCase(test.TestCase):
    def setUp(self):
        super(ReCreateBootImageTestCase, self).setUp()
        fake_src_cloud = mock.Mock()
        fake_dst_cloud = mock.Mock()
        self.cfg.set_override('ssh_user', 'fake_user', 'src')
        self.cfg.set_override('ssh_sudo_password', 'fake_sudo_password', 'src')
        fake_src_cloud.resources = {}
        fake_dst_cloud.resources = {}
        fake_init = {
            'src_cloud': fake_src_cloud,
            'dst_cloud': fake_dst_cloud,
            'cfg': self.cfg
        }
        self.obj = recreate_boot_image.ReCreateBootImage(fake_init)

    @mock.patch('cloudferrylib.os.actions.recreate_boot_image.'
                'ReCreateBootImage.process_images')
    def test_run_without_missing_images(self, mock_process_images):
        res = self.obj.run('fake_images_info')
        self.assertEqual({'images_info': 'fake_images_info',
                          'compute_ignored_images': {}},
                         res)
        self.assertIsZero(mock_process_images.call_count)

    @mock.patch('cloudferrylib.os.actions.recreate_boot_image.'
                'ReCreateBootImage.process_images')
    def test_run_with_missing_images(self, mock_process_images):
        mock_process_images.return_value = 'fake_new_images_info'
        res = self.obj.run({'images': 'fake_images_info_images'},
                           missing_images=['fake'])
        self.assertEqual({'images_info': {'images': 'fake_new_images_info'},
                          'compute_ignored_images': {}},
                         res)
        mock_process_images.assert_called_once_with('fake_images_info_images',
                                                    ['fake'])

    @mock.patch('cloudferrylib.os.actions.recreate_boot_image.'
                'ReCreateBootImage.restore_image')
    def test_process_images(self, mock_restore_image):
        missing_images = {1: 'fake_image_id_1', 2: 'fake_image_id_2'}
        images = {
            'fake_image_id_1': {
                'image': 'not empty'
            },
            'fake_image_id_2': {
                'image': {},
                'meta': {
                    'instance': [{
                        'diff': {
                            'host_src': 'fake_host_src',
                            'path_src': 'fake_path_src',
                        }
                    }]
                }
            }
        }
        expected_images = {
            'fake_image_id_1': {
                'image': 'not empty'
            },
            'fake_image_id_2': {
                'image': {
                    'id': 'fake_image_id_2',
                    'resource': None,
                    'checksum': 'fake_checksum',
                    'name': 'fake_name',
                    'size': 123456789,
                },
                'meta': {
                    'instance': [{
                        'diff': {
                            'host_src': 'fake_host_src',
                            'path_src': 'fake_path_src',
                        }
                    }]
                }
            }
        }
        new_image = mock.Mock()
        new_image.id = 'fake_image_id_2'
        new_image.checksum = 'fake_checksum'
        new_image.name = 'fake_name'
        new_image.size = 123456789
        mock_restore_image.return_value = new_image
        res = self.obj.process_images(images, missing_images)
        self.assertEqual(expected_images, res)
        mock_restore_image.assert_called_once_with('fake_image_id_2',
                                                   'fake_host_src',
                                                   'fake_path_src')

    @mock.patch('cloudferrylib.utils.remote_runner.RemoteRunner',
                new=mock.Mock)
    @mock.patch('cloudferrylib.utils.files.remote_file_size')
    @mock.patch('cloudferrylib.utils.file_proxy.FileProxy')
    @mock.patch('cloudferrylib.utils.files.RemoteStdout')
    def test_restore_image(self, mock_remote_stdout, mock_file_proxy,
                           mock_remote_file_size):
        mock_remote_file_size.return_value = 'fake_file_size'
        data = mock.Mock()
        mock_remote_stdout.return_value.__enter__.return_value.stdout = data
        qemu_img = mock.Mock()
        qemu_img.get_info.return_value.backing_filename = \
            'fake_backing_filename'
        qemu_img.get_info.return_value.format = 'fake_format'
        self.obj.src_cloud.qemu_img = qemu_img
        image_resource = mock.Mock()
        image_resource.create_image.return_value = 'fake_image'
        self.obj.dst_cloud.resources[utils.IMAGE_RESOURCE] = image_resource
        res = self.obj.restore_image('fake_image_id', 'fake_host',
                                     'fake_filename')
        self.assertEqual('fake_image', res)
        image_resource.create_image.assert_called_once_with(
            id='fake_image_id',
            name='restored image %s from host %s' % ('fake_image_id',
                                                     'fake_host'),
            container_format='bare',
            disk_format='fake_format',
            is_public=True,
            data=mock_file_proxy.return_value,
        )
        mock_file_proxy.assert_called_once_with(data,
                                                name='image fake_image_id',
                                                size='fake_file_size')
