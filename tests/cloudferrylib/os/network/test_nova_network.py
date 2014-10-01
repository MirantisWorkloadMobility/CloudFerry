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
from oslotest import mockpatch
from novaclient.v1_1 import client as nova_client
from cloudferrylib.os.network.nova_network import NovaNetwork
from tests import test

FAKE_CONFIG = {'user': 'fake_user',
               'password': 'fake_password',
               'tenant': 'fake_tenant',
               'host': 'fake_host'}


class TestNovaNetwork(test.TestCase):
    def setUp(self):
        super(TestNovaNetwork, self).setUp()

        self.nova_mock_client = mock.MagicMock()

        self.nova_client_patch = mockpatch.PatchObject(nova_client,
                                                       'Client',
                                                       new=self.nova_mock_client)

        self.useFixture(self.nova_client_patch)
        self.nova_network_client = NovaNetwork(FAKE_CONFIG)

        self.sg1 = mock.Mock()
        self.sg1.name = 'fake_name_1'
        self.sg1.description = 'fake_description_1'

        self.sg2 = mock.Mock()
        self.sg2.name = 'fake_name_2'
        self.sg2.description = 'fake_description_2'
        self.sg2.rules = []

        self.fake_instance = mock.Mock()


    def test_get_client(self):
        self.nova_mock_client.reset_mock()
        args = (FAKE_CONFIG['user'],
                FAKE_CONFIG['password'],
                FAKE_CONFIG['tenant'],
                "http://" + FAKE_CONFIG['host'] + ":35357/v2.0/")
        client = self.nova_network_client.get_client()
        self.nova_mock_client.assert_called_once_with(*args)

        self.assertEquals(self.nova_mock_client(), client)

    def test_get_security_groups(self):
        fake_security_groups = [self.sg1, self.sg2]
        self.nova_mock_client().security_groups.list.return_value = fake_security_groups
        security_groups = self.nova_network_client.get_security_groups()

        self.assertEquals(fake_security_groups, security_groups)
    
    def test_get_networks(self):
        fake_networks = [{'name': 'fake_name', 'ip': 'fake_ip', 'mac': 'fake_mac'},]

        self.fake_instance.networks.items.return_value = ([ 'fake_name', ['fake_ip',] ],)
        self.nova_network_client.get_mac_addresses = lambda x: iter(('fake_mac',))
        
        networks = self.nova_network_client.get_networks(self.fake_instance)

        self.assertEquals(fake_networks, networks)
   
    def test_upload_security_groups(self):
        fake_existing_groups = [self.sg1]
        fake_security_groups = [self.sg1, self.sg2]
        self.nova_mock_client().security_groups.list.return_value = fake_existing_groups
        
        self.nova_network_client.upload_security_groups(fake_security_groups)
        
        kwargs = {'name': 'fake_name_2',
                  'description': 'fake_description_2'}

        self.nova_mock_client().security_groups.create.assert_called_once_with(**kwargs)
