# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# pylint: disable=no-member

import mock

from novaclient import exceptions as nova_exc

from cloudferrylib.os.compute import cold_evacuate
from cloudferrylib.utils import utils

from tests import test


class ColdEvacuateTestCase(test.TestCase):
    config = utils.ext_dict(
        cloud=utils.ext_dict(
            ssh_user='ssh_user',
            ssh_sudo_password='ssh_sudo_password',
            ssh_host='ssh_host',
            host='host',
        ),
        migrate=utils.ext_dict(
            ssh_chunk_size=1337,
            retry=42,
        ),
    )

    def setUp(self):
        test.TestCase.setUp(self)

        self.server = self._make_server('fake-instance-id', status='ACTive')
        self.servers = {
            'fake-instance-id': self.server
        }

        self._services = {}
        self._make_service('nova-compute', 'fake-host-1', 'enabled')
        self._make_service('nova-compute', 'fake-host-2', 'enabled')
        self._make_service('nova-compute', 'fake-host-3', 'disabled')
        self._make_service('nova-compute', 'fake-host-4', 'disabled')
        self._make_service('nova-compute', 'fake-host-5', 'enabled')

        self.compute_api = mock.Mock()
        self.compute_api.servers.get.side_effect = self._servers_get
        self.compute_api.servers.delete.side_effect = self._servers_delete
        self.compute_api.servers.start.side_effect = self._servers_start
        self.compute_api.servers.stop.side_effect = self._servers_stop
        self.compute_api.servers.migrate.side_effect = self._migrate
        self.compute_api.servers.confirm_resize.side_effect = \
            self._confirm_resize

        self.compute_api.services.list.side_effect = self._services_list
        self.compute_api.services.disable.side_effect = self._service_disable
        self.compute_api.services.enable.side_effect = self._service_enable

        cfglib_conf_patcher = mock.patch('cfglib.CONF')
        self.addCleanup(cfglib_conf_patcher.stop)
        self.cfglib_conf = cfglib_conf_patcher.start()
        self.cfglib_conf.evacuation.state_change_timeout = 1
        self.cfglib_conf.evacuation.nova_home_path = '/fake/home'
        self.cfglib_conf.evacuation.nova_user = 'fakeuser'

        remote_runner_patcher = mock.patch(
            'cloudferrylib.utils.remote_runner.RemoteRunner')
        self.addCleanup(remote_runner_patcher.stop)
        self.remote_runner = remote_runner_patcher.start()

    def _servers_get(self, server_id):
        if not isinstance(server_id, basestring):
            server_id = server_id.id
        if server_id not in self.servers:
            raise nova_exc.NotFound(404)
        return self.servers[server_id]

    def _servers_delete(self, server_id):
        if not isinstance(server_id, basestring):
            server_id = server_id.id
        if server_id not in self.servers:
            raise nova_exc.NotFound(404)
        del self.servers[server_id]

    def _servers_stop(self, server_id):
        self._servers_get(server_id).status = 'SHUTOFF'

    def _servers_start(self, server_id):
        self._servers_get(server_id).status = 'ACTIVE'

    def _migrate(self, server_id):
        server = self._servers_get(server_id)
        server.status = 'VERIFY_RESIZE'
        services = [
            s for s in self._services.values()
            if s.status == 'enabled' and s.binary == 'nova-compute' and
            s.host != getattr(s, cold_evacuate.INSTANCE_HOST_ATTRIBUTE)]
        # concatenate all host names to fail test when there is any choice

        setattr(server, cold_evacuate.INSTANCE_HOST_ATTRIBUTE,
                ','.join(s.host for s in services))

    def _confirm_resize(self, server_id):
        self._servers_get(server_id).status = 'ACTIVE'

    def _make_server(self, instance_id, name='fake-instance', status='active',
                     image='fake-image-id', flavor='fake-flavor-id',
                     availability_zone='fake-az:fake-host',
                     block_device_mapping=None, nics=None):
        if block_device_mapping is None:
            block_device_mapping = {'/dev/vdb': 'volume-1',
                                    '/dev/vdc': 'volume-2'}
        _, host = availability_zone.split(':')
        server = mock.Mock()
        server.id = instance_id
        server.name = name
        server.status = status
        server.image = {'id': image}
        server.flavor = {'id': flavor}
        setattr(server, cold_evacuate.INSTANCE_HOST_ATTRIBUTE, host)
        server.block_device_mapping = block_device_mapping
        server.user_id = 'fake-user-id'
        server.nics = nics
        return server

    def _services_list(self, binary=None):
        services = sorted(self._services.values(), key=lambda x: x.host)
        return [s for s in services if s.binary == binary]

    def _make_service(self, binary, host, status):
        service = mock.MagicMock()
        service.binary = binary
        service.host = host
        service.status = status
        self._services[(binary, host)] = service

    def _service_disable(self, host, binary):
        self._services[binary, host].status = 'disabled'

    def _service_enable(self, host, binary):
        self._services[binary, host].status = 'enabled'

    def test_cold_evacuate(self):
        cold_evacuate.cold_evacuate(self.config, self.compute_api, self.server,
                                    'fake-host-5')

        # Check that services are restored after migration
        self.assertEqual(self._services['nova-compute', 'fake-host-1'].status,
                         'enabled')
        self.assertEqual(self._services['nova-compute', 'fake-host-2'].status,
                         'enabled')
        self.assertEqual(self._services['nova-compute', 'fake-host-3'].status,
                         'disabled')
        self.assertEqual(self._services['nova-compute', 'fake-host-4'].status,
                         'disabled')
        self.assertEqual(self._services['nova-compute', 'fake-host-5'].status,
                         'enabled')

        # Check that server migrated to right host
        self.assertEqual(
            getattr(self.server, cold_evacuate.INSTANCE_HOST_ATTRIBUTE),
            'fake-host-5')
