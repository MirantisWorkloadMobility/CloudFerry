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
import cfglib

from cloudferrylib.os.compute import nova_compute
from cloudferrylib.utils import timeout_exception
from cloudferrylib.utils import utils

from tests import test


FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'auth_url': 'http://1.1.1.1:35357/v2.0/'}),
    mysql=utils.ext_dict({'host': '1.1.1.1'}),
    migrate=utils.ext_dict({'migrate_quotas': True,
                            'speed_limit': '10MB',
                            'retry': '7',
                            'time_wait': 5}))


class NovaComputeTestCase(test.TestCase):
    def setUp(self):
        super(NovaComputeTestCase, self).setUp()

        self.mock_client = mock.MagicMock()
        self.nc_patch = mockpatch.PatchObject(nova_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.nc_patch)

        self.identity_mock = mock.Mock()

        self.fake_cloud = mock.Mock()
        self.fake_cloud.resources = dict(identity=self.identity_mock)
        self.fake_cloud.position = 'src'

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

    def test_get_nova_client(self):
        # To check self.mock_client call only from this test method
        self.mock_client.reset_mock()

        client = self.nova_client.get_client()

        self.mock_client.assert_called_once_with('fake_user', 'fake_password',
                                                 'fake_tenant',
                                                 'http://1.1.1.1:35357/v2.0/')
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

    def test_get_instances_list(self):
        fake_instances_list = [self.fake_instance_0, self.fake_instance_1]
        self.mock_client().servers.list.return_value = fake_instances_list
        test_args = {'marker': None,
                     'detailed': True,
                     'limit': None,
                     'search_opts': None}

        cfglib.init_config()
        instances_list = self.nova_client.get_instances_list(**test_args)

        self.mock_client().servers.list.assert_called_once_with(**test_args)
        self.assertEqual(fake_instances_list, instances_list)

    def test_get_status(self):
        self.fake_getter.get('fake_id').status = 'start'

        status = self.nova_client.get_status(self.fake_getter, 'fake_id')

        self.assertEqual('start', status)

    @mock.patch('cloudferrylib.os.compute.nova_compute.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_active(self, mock_get, mock_sleep):
        mock_get.return_value = 'shutoff'
        self.nova_client.change_status('active', instance=self.fake_instance_0)
        self.fake_instance_0.start.assert_called_once_with()
        mock_sleep.assert_called_with(2)

    @mock.patch('cloudferrylib.os.compute.nova_compute.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_shutoff(self, mock_get, mock_sleep):
        mock_get.return_value = 'active'
        self.nova_client.change_status('shutoff',
                                       instance=self.fake_instance_0)
        self.fake_instance_0.stop.assert_called_once_with()
        mock_sleep.assert_called_with(2)

    @mock.patch('cloudferrylib.os.compute.nova_compute.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_resume(self, mock_get, mock_sleep):
        mock_get.return_value = 'suspended'
        self.nova_client.change_status('active', instance=self.fake_instance_0)
        self.fake_instance_0.resume.assert_called_once_with()
        mock_sleep.assert_called_with(2)

    @mock.patch('cloudferrylib.os.compute.nova_compute.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_paused(self, mock_get, mock_sleep):
        mock_get.return_value = 'active'
        self.nova_client.change_status('paused', instance=self.fake_instance_0)
        self.fake_instance_0.pause.assert_called_once_with()
        mock_sleep.assert_called_with(2)

    @mock.patch('cloudferrylib.os.compute.nova_compute.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_unpaused(self, mock_get, mock_sleep):
        mock_get.return_value = 'paused'
        self.nova_client.change_status('active',
                                       instance=self.fake_instance_0)
        self.fake_instance_0.unpause.assert_called_once_with()
        mock_sleep.assert_called_with(2)

    @mock.patch('cloudferrylib.os.compute.nova_compute.time.sleep')
    @mock.patch('cloudferrylib.os.compute.nova_compute.NovaCompute.get_status')
    def test_change_status_suspend(self, mock_get, mock_sleep):
        mock_get.return_value = 'active'
        self.nova_client.change_status('suspended',
                                       instance=self.fake_instance_0)
        self.fake_instance_0.suspend.assert_called_once_with()
        mock_sleep.assert_called_with(2)

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

    def test_nothing_is_filtered_if_skip_down_hosts_option_not_set(self):
        cfglib.init_config()
        cfglib.CONF.migrate.skip_down_hosts = False
        self.fake_instance_0.host = 'host1'
        self.fake_instance_1.host = 'host2'

        hosts_down = ['host1', 'host2', 'host3']
        instances = [self.fake_instance_0, self.fake_instance_1]

        filtered = nova_compute.filter_down_hosts(hosts_down, instances)

        self.assertEqual(filtered, instances)

    def test_down_hosts_has_no_hosts_in_up_state(self):
        def service(hostname, state):
            s = mock.Mock()
            s.host = hostname
            s.state = state
            return s

        num_up_services = 5
        num_down_services = 10
        services = [service('uphost%d' % i, 'up')
                    for i in xrange(num_up_services)]
        services.extend([service('downhost%d' % i, 'down')
                         for i in xrange(num_down_services)])
        client = mock.Mock()
        client.services.list.return_value = services

        hosts = nova_compute.down_hosts(client)

        self.assertEqual(len(hosts), num_down_services)

    def test_down_hosts_are_filtered_if_config_option_is_set(self):
        def instance(hostname):
            inst = mock.Mock()
            setattr(inst, nova_compute.INSTANCE_HOST_ATTRIBUTE, hostname)
            return inst

        num_instances_up = 5
        num_hosts_down = 10
        hosts_down = ['downhost%d' % i for i in xrange(num_hosts_down)]
        instances = [instance('host%d' % i) for i in xrange(num_instances_up)]
        instances.extend([instance(host_down) for host_down in hosts_down])
        cfglib.init_config()
        cfglib.CONF.migrate.skip_down_hosts = True

        filtered = nova_compute.filter_down_hosts(
            hosts_down=hosts_down, elements=instances,
            hostname_attribute=nova_compute.INSTANCE_HOST_ATTRIBUTE)

        self.assertEqual(len(filtered), num_instances_up)


class DeployInstanceWithManualScheduling(test.TestCase):
    def test_tries_to_boot_vm_on_all_nodes(self):
        compute_hosts = ['host1', 'host2', 'host3']
        num_computes = len(compute_hosts)
        instance = {'availability_zone': 'somezone', 'name': 'vm1'}
        create_params = {'name': 'vm1'}
        client_conf = mock.Mock()

        nc = mock.Mock()
        nc.get_compute_hosts.return_value = compute_hosts
        nc.deploy_instance.side_effect = timeout_exception.TimeoutException(
            None, None, None)

        deployer = nova_compute.RandomSchedulerVmDeployer(nc)
        self.assertRaises(
            nova_compute.DestinationCloudNotOperational,
            deployer.deploy, instance, create_params, client_conf)
        self.assertEqual(nc.deploy_instance.call_count, num_computes)

    def test_runs_only_one_boot_if_node_is_good(self):
        compute_hosts = ['host1', 'host2', 'host3']
        instance = {'availability_zone': 'somezone'}
        create_params = {'name': 'vm1'}
        client_conf = mock.Mock()

        nc = mock.Mock()
        nc.get_compute_hosts.return_value = compute_hosts

        deployer = nova_compute.RandomSchedulerVmDeployer(nc)
        deployer.deploy(instance, create_params, client_conf)

        self.assertEqual(nc.deploy_instance.call_count, 1)


class FlavorDeploymentTestCase(test.TestCase):
    def test_flavor_is_updated_with_destination_id(self):
        config = mock.Mock()
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        expected_id = 'flavor1'
        existing_flavor = mock.Mock()
        existing_flavor.id = 'non-public-flavor'
        existing_flavor.name = 'non-public-flavor'
        created_flavor = mock.Mock()
        created_flavor.id = expected_id
        nc = nova_compute.NovaCompute(config, cloud)
        nc.get_flavor_list = mock.MagicMock()
        nc.get_flavor_list.return_value = [existing_flavor]
        nc.add_flavor_access = mock.MagicMock()
        nc._create_flavor_if_not_exists = mock.MagicMock()
        nc._create_flavor_if_not_exists.return_value = created_flavor

        flavors = {
            expected_id: {
                'flavor': {
                    'is_public': True,
                    'name': 'flavor1',
                    'tenants': []
                },
                'meta': {}
            },
            existing_flavor.id: {
                'flavor': {
                    'is_public': False,
                    'name': existing_flavor.name,
                    'tenants': ['t1', 't2']
                },
                'meta': {}
            }

        }

        tenant_map = {
            't1': 't1dest',
            't2': 't2dest',
        }
        nc._deploy_flavors(flavors, tenant_map)

        for f in flavors:
            self.assertTrue('id' in flavors[f]['meta'])
            self.assertEqual(flavors[f]['meta']['id'], f)

    def test_flavor_is_not_created_if_already_exists_on_dest(self):
        existing_flavor = mock.Mock()
        existing_flavor.id = 'existing-id'
        existing_flavor.name = 'existing-name'

        flavors = {
            existing_flavor.id: {
                'flavor': {
                    'is_public': True,
                    'name': existing_flavor.name,
                    'tenants': []
                },
                'meta': {}
            }
        }

        config = mock.Mock()
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        nc = nova_compute.NovaCompute(config, cloud)
        nc._create_flavor_if_not_exists = mock.Mock()
        nc.get_flavor_list = mock.Mock()
        nc.get_flavor_list.return_value = [existing_flavor]
        nc._deploy_flavors(flavors, tenant_map={})

        assert not nc._create_flavor_if_not_exists.called

    def test_access_not_updated_for_public_flavors(self):
        flavors = {
            'flavor1': {
                'flavor': {
                    'is_public': True,
                    'name': 'flavor1',
                    'tenants': []
                },
                'meta': {}
            }
        }
        tenant_map = {}
        config = mock.Mock()
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        nc = nova_compute.NovaCompute(config, cloud)
        nc._create_flavor_if_not_exists = mock.Mock()
        nc._add_flavor_access_for_tenants = mock.Mock()
        nc.get_flavor_list = mock.Mock()
        nc.get_flavor_list.return_value = []

        nc._deploy_flavors(flavors, tenant_map)

        assert not nc._add_flavor_access_for_tenants.called

    def test_access_list_is_updated_for_non_public_flavors(self):
        flavors = {
            'flavor1': {
                'flavor': {
                    'is_public': False,
                    'name': 'flavor1',
                    'tenants': []
                },
                'meta': {}
            }
        }
        tenant_map = {}
        config = mock.Mock()
        cloud = mock.MagicMock()
        cloud.position = 'dst'

        nc = nova_compute.NovaCompute(config, cloud)
        nc._create_flavor_if_not_exists = mock.Mock()
        nc._add_flavor_access_for_tenants = mock.Mock()
        nc.get_flavor_list = mock.Mock()
        nc.get_flavor_list.return_value = []

        nc._deploy_flavors(flavors, tenant_map)

        assert nc._add_flavor_access_for_tenants.called
