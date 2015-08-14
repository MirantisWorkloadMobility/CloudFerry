# Copyright 2015: Mirantis Inc.
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


import copy

import mock

from cloudferrylib.os.storage import cinder_database
from cloudferrylib.os.storage import cinder_netapp
from cloudferrylib.utils import utils
from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'host': '1.1.1.1',
                          'auth_url': 'http://1.1.1.1:35357/v2.0/'}),
    mysql=utils.ext_dict({'host': '1.1.1.1'}),
    migrate=utils.ext_dict({
        'retry': '7',
        'time_wait': 5}))

FAKE_ENTRY_0 = {'id': 'fake_volume_id_0',
                'host': 'c1',
                'provider_location': 'fake_netapp_server_0:/vol/v00_cinder'}

FAKE_ENTRY_1 = {'id': 'fake_volume_id_1',
                'host': 'c2@another_wrong_id',
                'provider_location': 'fake_netapp_server_1:/vol/v01_cinder'}


class CinderNetAppTestCase(test.TestCase):
    def setUp(self):
        super(CinderNetAppTestCase, self).setUp()

        self.identity_mock = mock.Mock()

        self.fake_cloud = mock.Mock()
        self.fake_cloud.position = 'src'
        self.fake_cloud.resources = dict(identity=self.identity_mock)

        with mock.patch(
                'cloudferrylib.os.storage.cinder_storage.mysql_connector'):
            self.cinder_client = cinder_netapp.CinderNetApp(FAKE_CONFIG,
                                                            self.fake_cloud)

    def test_make_hostname(self):
        entry_0 = copy.deepcopy(FAKE_ENTRY_0)
        entry_1 = copy.deepcopy(FAKE_ENTRY_1)

        hostname_0 = self.cinder_client.make_hostname(entry=entry_0)
        hostname_1 = self.cinder_client.make_hostname(entry=entry_1)

        self.assertEquals('c1@fake_netapp_server_0', hostname_0)
        self.assertEquals('c2@fake_netapp_server_1', hostname_1)

    @mock.patch.object(cinder_database.CinderStorage, 'fix_entries')
    def test_fix_entries_another_table(self, mock_fix_entries):
        entry_0 = copy.deepcopy(FAKE_ENTRY_0)
        entry_1 = copy.deepcopy(FAKE_ENTRY_1)

        result = self.cinder_client.fix_entries(
            table_list_of_dicts=[entry_0, entry_1],
            table_name='quotas')

        self.assertIsNone(result)

        self.assertEquals(entry_0, FAKE_ENTRY_0)
        self.assertEquals(entry_1, FAKE_ENTRY_1)

        mock_fix_entries.assert_called_once_with([entry_0, entry_1], 'quotas')

    @mock.patch.object(cinder_database.CinderStorage, 'fix_entries')
    def test_fix_entries(self, mock_fix_entries):
        entry_0 = copy.deepcopy(FAKE_ENTRY_0)
        entry_1 = copy.deepcopy(FAKE_ENTRY_1)

        result = self.cinder_client.fix_entries(
            table_list_of_dicts=[entry_0, entry_1],
            table_name='volumes')

        self.assertIsNone(result)

        self.assertEquals('c1@fake_netapp_server_0', entry_0['host'])
        self.assertEquals('c2@fake_netapp_server_1', entry_1['host'])

        mock_fix_entries.assert_called_once_with([entry_0, entry_1], 'volumes')
