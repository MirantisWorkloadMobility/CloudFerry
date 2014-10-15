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
from cloudferrylib.utils import utils

FAKE_CONFIG = utils.ext_dict(cloud=utils.ext_dict({'user': 'fake_user',
                                                   'password': 'fake_password',
                                                   'tenant': 'fake_tenant',
                                                   'host': '1.1.1.1'}))


class CinderStorageTestCase(test.TestCase):
    def setUp(self):
        super(CinderStorageTestCase, self).setUp()
        self.mock_client = mock.Mock()
        self.cs_patch = mockpatch.PatchObject(cinder_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.cs_patch)
        self.identity_client = mock.Mock()
        self.cinder_client = cinder_storage.CinderStorage(FAKE_CONFIG, self.identity_client)

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
        image = {'os-volume_upload_image': {'image_id': "fake_body"}}
        self.mock_client().volumes.upload_to_image.return_value = (
            'fake_response', image)

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

        # volumes = []
        # for vol in info['storage']['volumes']:
        #     vol_for_deploy = self.convert(vol['volume'])
        #     volume = self.create_volume(**vol_for_deploy)
        #     vol['volume']['id'] = volume.id
        #     self.wait_for_status(volume.id, AVAILABLE)
        #     self.finish(vol)
        #     self.attach_volume_to_instance(vol)
        #     volumes.append(volume)
        # return volumes

    # def convert(self, vol):
    #     info = {
    #         'size': vol['volume']['size'],
    #         'display_name': vol['volume']['display_name'],
    #         'display_description': vol['volume']['display_description'],
    #         'volume_type': vol['volume']['volume_type'],
    #         'availability_zone': vol['volume']['availability_zone'],
    #     }
    #     if 'image' in vol['meta']:
    #         if vol['meta']['image']:
    #             info['imageRef'] = vol['meta']['image']['id']
    #     return info

    def test_deploy(self):
        vol = {'volume': {
            'size': 'size1',
            'display_name': 'display_name1',
            'display_description': 'display_description1',
            'volume_type': 'volume_type1',
            'availability_zone': 'availability_zone1'
        },
               'meta': {
                   'image': {
                       'id': 'image_id1'
                   }
               }}
        info = {'storage': {'volumes': [vol]}}
        create_volume = mock.Mock()
        vol_return = mock.Mock(id="id2")
        create_volume.return_value = vol_return
        wait_for_status = mock.Mock()
        finish = mock.Mock()
        attach_volume_to_instance = mock.Mock()
        self.cinder_client.create_volume = create_volume
        self.cinder_client.wait_for_status = wait_for_status
        self.cinder_client.finish = finish
        self.cinder_client.attach_volume_to_instance = attach_volume_to_instance
        res = self.cinder_client.deploy(info)
        self.assertIn(vol_return, res)

    def test_read_info(self):
        temp = self.cinder_client.get_volumes_list
        self.cinder_client.get_volumes_list = mock.Mock()
        vol1 = mock.Mock(id="id1",
                         size='size',
                         display_name='display_name',
                         display_description='display_description',
                         availability_zone='availability_zone',
                         volume_type='volume_type',
                         attachments=[{'device': 'device'}],
                         bootable='bootable')
        self.cinder_client.get_volumes_list.return_value = [vol1]
        res = self.cinder_client.read_info(id="id1")
        self.assertIn('storage', res)
        self.assertIn('volumes', res['storage'])
        self.assertEqual(1, len(res['storage']['volumes']))
        self.assertEqual(vol1.id, res['storage']['volumes'][0]['volume']['id'])
        self.assertIn('image', res['storage']['volumes'][0]['meta'])
        self.cinder_client.get_volumes_list = temp

            # volume = {
            #     'id': vol.id,
            #     'size': vol.size,
            #     'display_name': vol.display_name,
            #     'display_description': vol.display_description,
            #     'volume_type': vol.volume_type,
            #     'availability_zone': vol.availability_zone,
            #     'device': vol.attachments[0]['device'] if vol.attachments else None,
            #     'bootable': vol.bootable,
            # }