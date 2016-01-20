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

import mock

from cloudferrylib.os.compute import instance_info_caches

from tests import test


class InstanceInfoCachesTestCase(test.TestCase):
    def setUp(self):
        super(InstanceInfoCachesTestCase, self).setUp()

        self.conn = mock.Mock()
        self.instance_info_caches = instance_info_caches.InstanceInfoCaches(
            self.conn)

    def test_get_info_caches(self):
        self.conn.execute.return_value.fetchone.return_value = 'fake'
        res = self.instance_info_caches.get_info_caches('fake_id')
        self.assertEqual('fake', res)
        self.conn.execute.assert_called_once_with(
            instance_info_caches.InstanceInfoCaches.GET_INSTANCE_INFO,
            uuid='fake_id')

    @mock.patch('json.loads')
    def test_get_network_info(self, mock_loads):
        mock_loads.return_value = 'fake'
        with mock.patch.object(
                self.instance_info_caches, 'get_info_caches',
                return_value={'network_info': 'fake_info_caches'}) as m:
            res = self.instance_info_caches.get_network_info('fake_id')
            self.assertEqual('fake', res)
            m.assert_called_once_with('fake_id')
        mock_loads.assert_called_once_with('fake_info_caches')

    def test_enumerate_addresses(self):
        with mock.patch.object(
            self.instance_info_caches, 'get_network_info',
            return_value=[{'address': 'fake_1'},
                          {'address': 'fake_2'}]) as m:
            res = self.instance_info_caches.enumerate_addresses('fake_id')
            self.assertEqual({'fake_1': 0, 'fake_2': 1}, res)
            m.assert_called_once_with('fake_id')
