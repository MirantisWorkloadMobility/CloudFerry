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

from cloudferrylib.os.storage import cinder_storage
from tests import test
from oslotest import mockpatch

from cinderclient.v1 import client as cinder_client


FAKE_CONFIG = {'user': 'fake_user',
               'password': 'fake_password',
               'tenant': 'fake_tenant',
               'host': '1.1.1.1'}


class CinderStorageTestCase(test.TestCase):
    def setUp(self):
        super(CinderStorageTestCase, self).setUp()
        self.mock_client = mock.Mock()
        self.cs_patch = mockpatch.PatchObject(cinder_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.cs_patch)
        self.cinder_client = cinder_storage.CinderStorage(FAKE_CONFIG)

        self.fake_volume_0 = mock.Mock()
        self.fake_volume_1 = mock.Mock()

        self.mock_client().volumes.get.return_value = self.fake_volume_0

    def test_get_cinder_client(self):
        # To check self.mock_client call only from this test method
        self.mock_client.reset_mock()

        client = self.cinder_client.get_cinder_client(FAKE_CONFIG)

        self.mock_client.assert_called_once_with('fake_user', 'fake_password',
                                                 'fake_tenant',
                                                 'http://1.1.1.1:35357/v2.0/')
        self.assertEqual(self.mock_client(), client)

    def test_get_volumes_list(self):
        fake_volume_list = [self.fake_volume_0, self.fake_volume_1]
        self.mock_client().volumes.list.return_value = fake_volume_list

        volumes_list = self.cinder_client.get_volumes_list()

        self.mock_client().volumes.list.assert_called_once_with(True, None)
        self.assertEqual(volumes_list, fake_volume_list)

    def test_create_volume(self):
        self.mock_client().volumes.create.return_value = self.fake_volume_0

        volume = self.cinder_client.create_volume(100500, name='fake')

        self.mock_client().volumes.create.assert_called_once_with(100500,
                                                                  name='fake')
        self.assertEqual(self.fake_volume_0, volume)

    def test___get_volume_by_id(self):
        volume = self.cinder_client._CinderStorage__get_volume_by_id('fake_id')

        self.mock_client().volumes.get.assert_called_once_with('fake_id')
        self.assertEqual(self.fake_volume_0, volume)

    def test_delete_volume(self):
        self.cinder_client.delete_volume('fake_id')

        self.mock_client().volumes.get.assert_called_once_with('fake_id')
        self.mock_client().volumes.delete.assert_called_once_with(
            self.fake_volume_0)

    def test_update_volume(self):
        self.cinder_client.update_volume('fake_id', name='new_fake_name')

        self.mock_client().volumes.get.assert_called_once_with('fake_id')
        self.mock_client().volumes.update.assert_called_once_with(
            self.fake_volume_0, name='new_fake_name')

    def test_attach_volume(self):
        self.mock_client().volumes.attach.return_value = (
            'fake_response', 'fake_body')

        response, body = self.cinder_client.attach_volume('fake_vol_id',
                                                          'fake_instance_id',
                                                          '/fake/mountpoint')

        test_args = {'instance_uuid': 'fake_instance_id',
                     'mountpoint': '/fake/mountpoint',
                     'mode': 'rw'}

        self.mock_client().volumes.get.assert_called_once_with('fake_vol_id')
        self.mock_client().volumes.attach.assert_called_once_with(
            self.fake_volume_0, **test_args)
        self.assertEqual(('fake_response', 'fake_body'), (response, body))

    def test_detach_volume(self):
        self.mock_client().volumes.detach.return_value = (
            'fake_response', 'fake_body')

        response, body = self.cinder_client.detach_volume('fake_vl_id')

        self.mock_client().volumes.detach.assert_called_once_with('fake_vl_id')
        self.assertEqual(('fake_response', 'fake_body'), (response, body))

    def test_upload_volume_to_image(self):
        self.mock_client().volumes.upload_to_image.return_value = (
            'fake_response', 'fake_body')

        response, body = self.cinder_client.upload_volume_to_image(
            'fake_vol_id', True, 'fake_image_name', 'fake_cont_format',
            'fake_disk_format')

        test_args = {'volume': self.fake_volume_0,
                     'container_format': 'fake_cont_format',
                     'force': True,
                     'image_name': 'fake_image_name',
                     'disk_format': 'fake_disk_format'}

        self.mock_client().volumes.get.assert_called_once_with('fake_vol_id')
        self.mock_client().volumes.upload_to_image.assert_called_once_with(
            **test_args)
        self.assertEqual(('fake_response', 'fake_body'), (response, body))
