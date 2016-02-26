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

from novaclient.v1_1 import client as nova_client
from oslotest import mockpatch

from cloudferrylib.base import exception
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.utils import utils

from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'region': None,
                          'auth_url': 'http://1.1.1.1:35357/v2.0/',
                          'cacert': '',
                          'insecure': False}),
    mysql=utils.ext_dict({'host': '1.1.1.1'}),
    migrate=utils.ext_dict({'migrate_quotas': True,
                            'retry': '7',
                            'time_wait': 5,
                            'keep_network_interfaces_order': True,
                            'keep_usage_quotas_inst': True,
                            'override_rules': None}))


class BaseNovaComputeTestCase(test.TestCase):
    def setUp(self):
        super(BaseNovaComputeTestCase, self).setUp()

        self.mock_client = mock.MagicMock()
        self.nc_patch = mockpatch.PatchObject(nova_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.nc_patch)

        self.identity_mock = mock.Mock()

        self.fake_cloud = mock.Mock()
        self.fake_cloud.resources = dict(identity=self.identity_mock)
        self.fake_cloud.position = 'src'
        self.fake_cloud.config = FAKE_CONFIG

        with mock.patch(
                'cloudferrylib.os.compute.nova_compute.mysql_connector'):
            self.nova_client = nova_compute.NovaCompute(FAKE_CONFIG,
                                                        self.fake_cloud)

        self.fake_instance_0 = mock.Mock()
        self.fake_instance_1 = mock.Mock()
        self.fake_instance_0.id = 'fake_instance_id'

        self.fake_getter = mock.Mock()

        self.fake_flavor_0 = mock.Mock()
        self.fake_flavor_1 = mock.Mock()

        self.fake_tenant_quota_0 = mock.Mock()


class NovaComputeTestCase(BaseNovaComputeTestCase):
    def test_get_nova_client(self):
        # To check self.mock_client call only from this test method
        self.mock_client.reset_mock()

        client = self.nova_client.get_client()

        self.mock_client.assert_called_once_with('fake_user', 'fake_password',
                                                 'fake_tenant',
                                                 'http://1.1.1.1:35357/v2.0/',
                                                 cacert='', insecure=False,
                                                 region_name=None)
        self.assertEqual(self.mock_client(), client)

    def test_create_instance(self):
        ncli = mock.Mock()
        ncli.servers.create.return_value = self.fake_instance_0

        instance_id = self.nova_client.create_instance(nclient=ncli,
                                                       name='fake_instance',
                                                       image='fake_image',
                                                       flavor='fake_flavor',
                                                       user_id='some-id')

        self.assertEqual('fake_instance_id', instance_id)

    def test_get_status(self):
        self.mock_client().servers.get('fake_id').status = 'start'

        status = self.nova_client.get_status('fake_id')

        self.assertEqual('start', status)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_active(self, mock_get, mock_sleep):
        mock_get.return_value = 'shutoff'
        self.nova_client.change_status('active', instance=self.fake_instance_0)
        self.fake_instance_0.start.assert_called_once_with()
        mock_sleep.assert_called_with(32)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_shutoff(self, mock_get, mock_sleep):
        mock_get.return_value = 'active'
        self.nova_client.change_status('shutoff',
                                       instance=self.fake_instance_0)
        self.fake_instance_0.stop.assert_called_once_with()
        mock_sleep.assert_called_with(32)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_resume(self, mock_get, mock_sleep):
        mock_get.return_value = 'suspended'
        self.nova_client.change_status('active', instance=self.fake_instance_0)
        self.fake_instance_0.resume.assert_called_once_with()
        mock_sleep.assert_called_with(32)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_paused(self, mock_get, mock_sleep):
        mock_get.return_value = 'active'
        self.nova_client.change_status('paused', instance=self.fake_instance_0)
        self.fake_instance_0.pause.assert_called_once_with()
        mock_sleep.assert_called_with(32)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_unpaused(self, mock_get, mock_sleep):
        mock_get.return_value = 'paused'
        self.nova_client.change_status('active',
                                       instance=self.fake_instance_0)
        self.fake_instance_0.unpause.assert_called_once_with()
        mock_sleep.assert_called_with(32)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_suspend(self, mock_get, mock_sleep):
        mock_get.return_value = 'active'
        self.nova_client.change_status('suspended',
                                       instance=self.fake_instance_0)
        self.fake_instance_0.suspend.assert_called_once_with()
        mock_sleep.assert_called_with(32)

    def test_change_status_same(self):
        self.mock_client().servers.get('fake_instance_id').status = 'stop'

        self.nova_client.change_status('stop', instance=self.fake_instance_0)
        self.assertFalse(self.fake_instance_0.stop.called)

    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.'
                'wait_for_status')
    def test_shutoff_to_verify_resize_brings_instance_active(self, _):
        self.mock_client().servers.get('fake_instance_id').status = 'shutoff'

        self.nova_client.change_status('verify_resize',
                                       instance=self.fake_instance_0)

        self.assertTrue(self.fake_instance_0.start.called)

    def test_get_flavor_from_id(self):
        self.mock_client().flavors.find.return_value = self.fake_flavor_0

        flavor = self.nova_client.get_flavor_from_id('fake_flavor_id')

        self.assertEqual(self.fake_flavor_0, flavor)

    def test_get_flavor_list(self):
        fake_flavor_list = [self.fake_flavor_0, self.fake_flavor_1]
        self.mock_client().flavors.list.return_value = fake_flavor_list

        flavor_list = self.nova_client.get_flavor_list()

        self.assertEqual(fake_flavor_list, flavor_list)

    def test_create_flavor(self):
        self.mock_client().flavors.create.return_value = self.fake_flavor_0

        flavor = self.nova_client.create_flavor()

        self.assertEqual(self.fake_flavor_0, flavor)

    def test_delete_flavor(self):
        self.nova_client.delete_flavor('fake_fl_id')

        self.mock_client().flavors.delete.assert_called_once_with('fake_fl_id')

    def test_get_quotas(self):
        self.mock_client().quotas.get.return_value = self.fake_tenant_quota_0
        tenant_quota = self.nova_client.get_quotas('fake_tenant_id')

        self.assertEqual(self.fake_tenant_quota_0, tenant_quota)

    def test_update_quota(self):
        self.nova_client.update_quota('fake_tenant_id',
                                      instances='new_fake_value')

        self.mock_client().quotas.update.assert_called_once_with(
            tenant_id='fake_tenant_id',
            user_id=None,
            instances='new_fake_value')

    def _test_get_networks(self, instance_network_info,
                           keep_network_interfaces_order):
        instance = mock.Mock()
        instance.id = 'fake_instance_id'
        network_resource = mock.Mock()
        network_resource.get_instance_network_info.\
            return_value = instance_network_info
        self.nova_client.cloud.resources = {
            utils.NETWORK_RESOURCE: network_resource}
        self.nova_client.config.migrate.\
            keep_network_interfaces_order = keep_network_interfaces_order
        res = self.nova_client.get_networks(instance)
        network_resource.get_instance_network_info.assert_called_once_with(
            'fake_instance_id')
        return res

    def test_get_networks_not_sorted(self):
        res = self._test_get_networks('fake', False)
        self.assertEqual('fake', res)

    @mock.patch('cloudferrylib.os.compute.instance_info_caches.'
                'InstanceInfoCaches.enumerate_addresses')
    def test_get_networks_with_sorting(self, mock_enumerate_addresses):
        unsorted_interfaces = [{'mac_address': 'fake_mac_1'},
                               {'mac_address': 'fake_mac_3'},
                               {'mac_address': 'fake_mac_2'}]
        sorted_interfaces = [{'mac_address': 'fake_mac_1'},
                             {'mac_address': 'fake_mac_2'},
                             {'mac_address': 'fake_mac_3'}]
        enumerated_addresses = {'fake_mac_1': 0,
                                'fake_mac_2': 1,
                                'fake_mac_3': 2}
        mock_enumerate_addresses.return_value = enumerated_addresses
        res = self._test_get_networks(unsorted_interfaces, True)
        for i, interface in enumerate(res):
            self.assertEqual(sorted_interfaces[i]['mac_address'],
                             interface['mac_address'])
        mock_enumerate_addresses.assert_called_once_with('fake_instance_id')


class ComputeHostsTestCase(BaseNovaComputeTestCase):
    @classmethod
    def _host(cls, name, up=True, enabled=True):
        h = mock.Mock()
        h.host = name
        h.host_name = name
        h.state = 'up' if up else 'down'
        h.status = 'enabled' if enabled else 'disabled'
        return h

    def test_down_hosts_are_skipped(self):
        active_host_names = ['active1', 'active2']
        down_host_names = ['down1', 'down2']

        down_hosts = [self._host(name, up=False) for name in down_host_names]
        active_hosts = [self._host(name) for name in active_host_names]
        all_hosts = active_hosts + down_hosts

        self.mock_client().services.list.return_value = all_hosts
        self.mock_client().hosts.list.return_value = all_hosts

        hosts = self.nova_client.get_compute_hosts()

        self.assertIsNotNone(hosts)
        self.assertTrue(isinstance(hosts, list))

        for active in active_host_names:
            self.assertIn(active, hosts)

        for down in down_host_names:
            self.assertNotIn(down, hosts)

    def test_disabled_hosts_are_skipped(self):
        active_host_names = ['active1', 'active2']
        disabled_host_names = ['disabled1', 'disabled2']

        disabled_hosts = [self._host(name, enabled=False)
                          for name in disabled_host_names]
        active_hosts = [self._host(name) for name in active_host_names]
        all_hosts = active_hosts + disabled_hosts

        self.mock_client().services.list.return_value = all_hosts
        self.mock_client().hosts.list.return_value = all_hosts

        hosts = self.nova_client.get_compute_hosts()

        self.assertIsNotNone(hosts)
        self.assertTrue(isinstance(hosts, list))

        for active in active_host_names:
            self.assertIn(active, hosts)

        for disabled in disabled_host_names:
            self.assertNotIn(disabled, hosts)

    def test_disabled_down_hosts_are_skipped(self):
        active_host_names = ['active1', 'active2']
        disabled_host_names = ['disabled1', 'disabled2', 'disabled3']

        disabled_hosts = [self._host(name, enabled=False, up=False)
                          for name in disabled_host_names]
        active_hosts = [self._host(name) for name in active_host_names]
        all_hosts = active_hosts + disabled_hosts

        self.mock_client().services.list.return_value = all_hosts
        self.mock_client().hosts.list.return_value = all_hosts

        hosts = self.nova_client.get_compute_hosts()

        self.assertIsNotNone(hosts)
        self.assertTrue(isinstance(hosts, list))

        for active in active_host_names:
            self.assertIn(active, hosts)

        for disabled in disabled_host_names:
            self.assertNotIn(disabled, hosts)

    def test_hosts_outside_availability_zone_are_not_shown(self):
        active_hosts = ['h1', 'h2', 'h3', 'h4', 'h5']
        # az == availability zone
        az_hosts = ['h1', 'h2']

        all_hosts = [self._host(name) for name in active_hosts]
        hosts_in_az = [self._host(name) for name in az_hosts]

        self.mock_client().services.list.return_value = all_hosts
        self.mock_client().hosts.list.return_value = hosts_in_az

        hosts = self.nova_client.get_compute_hosts(availability_zone='az')

        self.assertEqual(az_hosts, hosts)

    def test_disabled_hosts_from_availability_zone_are_not_shown(self):
        active_hosts = ['h1', 'h2', 'h3', 'h4', 'h5']
        # az == availability zone
        out_az_disabled_hosts = ['disabled1', 'disabled2', 'disabled3']
        disabled_az_hosts = ['az_disabled1', 'az_disabled2']
        disabled_hosts = out_az_disabled_hosts + disabled_az_hosts

        enabled_az_hosts = ['h1', 'h2']
        az_hosts = enabled_az_hosts

        all_hosts = [self._host(name) for name in active_hosts]
        all_hosts += [self._host(name, enabled=False)
                      for name in disabled_hosts]
        hosts_in_az = [self._host(name) for name in az_hosts] + \
                      [self._host(name, enabled=False)
                       for name in disabled_az_hosts]

        self.mock_client().services.list.return_value = all_hosts
        self.mock_client().hosts.list.return_value = hosts_in_az

        hosts = self.nova_client.get_compute_hosts(availability_zone='az')

        self.assertEqual(az_hosts, hosts)


class DeployInstanceWithManualScheduling(test.TestCase):
    def test_tries_to_boot_vm_on_all_nodes(self):
        compute_hosts = ['host1', 'host2', 'host3']
        num_computes = len(compute_hosts)
        create_params = {'name': 'vm1', 'availability_zone': 'somezone'}
        client_conf = mock.Mock()

        nc = mock.Mock()
        nc.get_availability_zone.return_value = 'nova'
        nc.get_compute_hosts.return_value = compute_hosts
        nc.deploy_instance.side_effect = exception.TimeoutException(
            None, None, None)

        deployer = nova_compute.RandomSchedulerVmDeployer(nc)
        self.assertRaises(
            nova_compute.DestinationCloudNotOperational,
            deployer.deploy, create_params, client_conf)
        self.assertEqual(nc.deploy_instance.call_count, num_computes + 1)

    def test_runs_only_one_boot_if_node_is_good(self):
        compute_hosts = ['host1', 'host2', 'host3']
        create_params = {'name': 'vm1', 'availability_zone': 'somezone'}
        client_conf = mock.Mock()

        nc = mock.Mock()
        nc.get_compute_hosts.return_value = compute_hosts

        deployer = nova_compute.RandomSchedulerVmDeployer(nc)
        deployer.deploy(create_params, client_conf)

        self.assertEqual(nc.deploy_instance.call_count, 1)


class FlavorDeploymentTestCase(test.TestCase):
    def test_flavor_is_not_created_if_already_exists_on_dest(self):
        existing_flavor = mock.Mock()
        existing_flavor.id = 'existing-id'
        existing_flavor.name = 'existing-name'
        existing_flavor.is_public = True
        existing_flavor.ram = 48
        existing_flavor.vcpus = 1
        existing_flavor.disk = 0
        existing_flavor.ephemeral = 1
        existing_flavor.swap = 0
        existing_flavor.rxtx_factor = 1.0

        flavors = {
            existing_flavor.id: {
                'flavor': {
                    'is_public': True,
                    'name': existing_flavor.name,
                    'tenants': [],
                    'ram': 48,
                    'vcpus': 1,
                    'disk': 0,
                    'ephemeral': 1,
                    'swap': 0,
                    'rxtx_factor': 1.0,
                },
                'meta': {}
            }
        }

        config = mock.Mock()
        config.migrate.override_rules = None
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        nc = nova_compute.NovaCompute(config, cloud)
        nc._create_flavor_if_not_exists = mock.Mock()
        nc.get_flavor_list = mock.Mock()
        nc.get_flavor_list.return_value = [existing_flavor]
        nc._deploy_flavors(flavors, tenant_map={})

        assert not nc._create_flavor_if_not_exists.called

    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute'
                '.create_flavor')
    def test_access_not_updated_for_public_flavors(self, _):
        flavors = {
            'flavor1': {
                'flavor': {
                    'is_public': True,
                    'name': 'flavor1',
                    'tenants': [],
                    'ram': 48,
                    'vcpus': 1,
                    'disk': 0,
                    'ephemeral': 1,
                    'swap': 0,
                    'rxtx_factor': 1.0,
                },
                'meta': {}
            }
        }
        tenant_map = {}
        config = mock.Mock()
        config.migrate.override_rules = None
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        nc = nova_compute.NovaCompute(config, cloud)
        nc._create_flavor_if_not_exists = mock.Mock()
        nc._add_flavor_access_for_tenants = mock.Mock()
        nc.get_flavor_list = mock.Mock()
        nc.get_flavor_list.return_value = []

        nc._deploy_flavors(flavors, tenant_map)

        assert not nc._add_flavor_access_for_tenants.called

    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute'
                '.create_flavor')
    def test_access_list_is_updated_for_non_public_flavors(self, _):
        flavors = {
            'flavor1': {
                'flavor': {
                    'is_public': False,
                    'name': 'flavor1',
                    'tenants': [],
                    'ram': 48,
                    'vcpus': 1,
                    'disk': 0,
                    'ephemeral': 1,
                    'swap': 0,
                    'rxtx_factor': 1.0,
                },
                'meta': {}
            }
        }
        tenant_map = {}
        config = mock.Mock()
        config.migrate.override_rules = None
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        nc = nova_compute.NovaCompute(config, cloud)
        nc._create_flavor_if_not_exists = mock.Mock()
        nc._add_flavor_access_for_tenants = mock.Mock()
        nc.get_flavor_list = mock.Mock()
        nc.get_flavor_list.return_value = []

        nc._deploy_flavors(flavors, tenant_map)

        assert nc._add_flavor_access_for_tenants.called


@mock.patch("cloudferrylib.os.compute.nova_compute.nova_client.Client")
class NovaClientTestCase(test.TestCase):
    def test_adds_region_if_set_in_config(self, n_client):
        cloud = mock.MagicMock()
        config = mock.MagicMock()

        tenant = 'tenant'
        region = 'region'
        user = 'user'
        auth_url = 'auth_url'
        password = 'password'
        insecure = False
        cacert = ''

        config.cloud.user = user
        config.cloud.tenant = tenant
        config.cloud.region = region
        config.cloud.auth_url = auth_url
        config.cloud.password = password
        config.cloud.insecure = insecure
        config.cloud.cacert = cacert
        config.migrate.override_rules = None

        cloud.position = 'src'

        n = nova_compute.NovaCompute(config, cloud)
        n.get_client()

        n_client.assert_called_with(user, password, tenant, auth_url,
                                    region_name=region, cacert=cacert,
                                    insecure=insecure)

    def test_does_not_add_region_if_not_set_in_config(self, n_client):
        cloud = mock.MagicMock()
        config = mock.MagicMock()

        tenant = 'tenant'
        user = 'user'
        auth_url = 'auth_url'
        password = 'password'
        insecure = False
        cacert = ''

        config.cloud.region = None
        config.cloud.user = user
        config.cloud.tenant = tenant
        config.cloud.auth_url = auth_url
        config.cloud.password = password
        config.cloud.insecure = insecure
        config.cloud.cacert = cacert
        config.migrate.override_rules = None

        cloud.position = 'src'

        n = nova_compute.NovaCompute(config, cloud)
        n.get_client()

        n_client.assert_called_with(user, password, tenant, auth_url,
                                    cacert=cacert, insecure=insecure,
                                    region_name=None)
