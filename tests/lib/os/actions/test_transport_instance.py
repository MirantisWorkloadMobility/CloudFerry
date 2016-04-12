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

from cloudferry.lib.base import exception
from cloudferry.lib.os.actions import transport_instance
from cloudferry.lib.utils import utils

from tests import test


class DeployInstanceWithManualScheduling(test.TestCase):

    @mock.patch("cloudferry.lib.os.network.network_utils.prepare_networks")
    @mock.patch("cloudferry.lib.os.network.network_utils.associate_floatingip")
    def test_tries_to_boot_vm_on_all_nodes(self,
                                           associate_floatingip,
                                           prepare_networks):

        compute_hosts = ['host1', 'host2', 'host3']
        num_computes = len(compute_hosts)
        instance_body = {'availability_zone': 'somezone', 'name': 'vm1'}
        one_instance = {
            utils.INSTANCES_TYPE: {
                'some_id': {
                    utils.INSTANCE_BODY: instance_body,
                }
            }
        }

        dst_compute = mock.Mock()
        dst_compute.get_compute_hosts.return_value = compute_hosts
        dst_compute.deploy.side_effect = exception.TimeoutException(
            None, None, None)

        dst_cloud = mock.Mock()
        dst_cloud.resources = {
            utils.COMPUTE_RESOURCE: dst_compute,
            utils.NETWORK_RESOURCE: mock.Mock(),
            utils.IDENTITY_RESOURCE: mock.Mock(),
        }

        tr_inst = transport_instance.TransportInstance(mock.MagicMock())
        tr_inst.cfg = mock.MagicMock()
        tr_inst.cfg.migrate.keep_ip = True
        tr_inst.cfg.migrate.keep_floatingip = True

        tr_inst.dst_cloud = dst_cloud

        self.assertRaises(
            transport_instance.DestinationCloudNotOperational,
            tr_inst._deploy_instance_on_random_host,
            one_instance,
            'somezone'
        )
        self.assertEqual(associate_floatingip.call_count, num_computes)
        self.assertEqual(prepare_networks.call_count, num_computes)
        self.assertEqual(dst_compute.deploy.call_count, num_computes)

    @mock.patch("cloudferry.lib.os.network.network_utils.prepare_networks")
    @mock.patch("cloudferry.lib.os.network.network_utils.associate_floatingip")
    def test_runs_only_one_boot_if_node_is_good(self,
                                                associate_floatingip,
                                                prepare_networks):
        compute_hosts = mock.MagicMock()
        compute_hosts.__iter__.return_value = ['host1', 'host2', 'host3']
        compute_hosts.pop.return_value = 'host2'

        instance_body = {'availability_zone': 'somezone', 'name': 'vm1'}
        one_instance = {
            utils.INSTANCES_TYPE: {
                'some_id': {
                    utils.INSTANCE_BODY: instance_body,
                }
            }
        }

        kwargs = {'availability_zone': 'somezone:host2'}

        updated_instance_body = {
            'availability_zone': 'somezone',
            'name': 'vm1',
            'nics': [{'floatingip': None,
                      'net-id': 'id',
                      'port-id': 'id'}]
        }
        updated_one_instance = {
            utils.INSTANCES_TYPE: {
                'some_id': {
                    utils.INSTANCE_BODY: updated_instance_body
                    }
            }
        }
        prepare_networks.return_value = updated_one_instance

        dst_compute = mock.Mock()
        dst_compute.get_compute_hosts.return_value = compute_hosts

        dst_cloud = mock.Mock()
        dst_cloud.resources = {
            utils.COMPUTE_RESOURCE: dst_compute,
            utils.NETWORK_RESOURCE: mock.Mock(),
            utils.IDENTITY_RESOURCE: mock.Mock(),
        }

        tr_inst = transport_instance.TransportInstance(mock.MagicMock())
        tr_inst.cfg = mock.MagicMock()
        tr_inst.cfg.migrate.keep_ip = True
        tr_inst.cfg.migrate.keep_floatingip = True

        tr_inst.dst_cloud = dst_cloud

        tr_inst._deploy_instance_on_random_host(
            one_instance, 'somezone'
        )

        prepare_networks.assert_called_once_with(
            one_instance,
            tr_inst.cfg.migrate.keep_ip,
            dst_cloud.resources[utils.NETWORK_RESOURCE],
            dst_cloud.resources[utils.IDENTITY_RESOURCE],
        )
        associate_floatingip.assert_called_once_with(
            prepare_networks.return_value,
            dst_cloud.resources[utils.NETWORK_RESOURCE]
        )
        dst_compute.deploy.assert_called_once_with(
            updated_instance_body,
            **kwargs
        )
        self.assertEqual(dst_compute.deploy.call_count, 1)
