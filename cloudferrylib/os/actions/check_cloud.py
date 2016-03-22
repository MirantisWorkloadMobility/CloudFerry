# Copyright 2015 Mirantis Inc.
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


import contextlib
import copy
import time

from cinderclient import exceptions as cinder_exc
from glanceclient import exc as glance_exc
from keystoneclient.openstack.common.apiclient import exceptions as ks_exc
from neutronclient.common import exceptions as neutron_exc
from novaclient import exceptions as nova_exc

from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.image import glance_image
from cloudferrylib.os.network import neutron
from cloudferrylib.os.storage import cinder_storage as cinder
from cloudferrylib.utils import log
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import retrying


LOG = log.getLogger(__name__)


class CheckCloud(action.Action):

    @contextlib.contextmanager
    def create_tenant(self, ks_client, tenant_name):
        LOG.info("Creating tenant '%s'...", tenant_name)
        tenant = ks_client.create_tenant(tenant_name)
        username = ks_client.config.cloud.user
        keystone_client = ks_client.keystone_client
        keystone_client.roles.add_user_role(
            user=keystone_client.users.find(name=username),
            role=keystone_client.roles.find(name='admin'),
            tenant=tenant)
        try:
            yield tenant
        finally:
            LOG.info("Deleting previously created tenant '%s'...", tenant_name)
            ks_client.delete_tenant(tenant)

    @contextlib.contextmanager
    def create_flavor(self, nv_client, flavor_info):
        LOG.info("Creating flavor '%s'...", flavor_info['name'])
        flavor = nv_client.create_flavor(**flavor_info)
        try:
            yield flavor.id
        finally:
            LOG.info("Deleting previously created flavor '%s'...", flavor.name)
            nv_client.delete_flavor(flavor)

    @contextlib.contextmanager
    def create_network(self, nt_client, network):
        LOG.info("Creating network '%s'...", network['network']['name'])
        net_id = nt_client.neutron_client.create_network(
            network)['network']['id']
        try:
            yield net_id
        finally:
            LOG.info("Deleting previously created network '%s'...",
                     network['network']['name'])
            nt_client.neutron_client.delete_network(net_id)

    @contextlib.contextmanager
    def create_subnet(self, nt_client, subnet_info):
        LOG.info("Creating subnet '%s'...", subnet_info['subnet']['name'])
        subnet_id = nt_client.neutron_client.create_subnet(
            subnet_info)['subnet']['id']
        try:
            yield
        finally:
            LOG.info("Deleting previously created subnet '%s'...",
                     subnet_info['subnet']['name'])
            nt_client.neutron_client.delete_subnet(subnet_id)

    @contextlib.contextmanager
    def create_image(self, gl_client, image_info):
        LOG.info("Creating image '%s'...", image_info['name'])
        image = gl_client.create_image(**image_info)
        try:
            yield image.id
        finally:
            LOG.info("Deleting previously created image '%s'...", image.name)
            gl_client.delete_image(image.id)

    @contextlib.contextmanager
    def create_volume(self, cn_client, volume_info):
        LOG.info("Creating volume '%s'...", volume_info['display_name'])
        volume = cn_client.create_volume(**volume_info)
        cn_client.wait_for_status(volume.id, cn_client.get_status, 'available')
        try:
            yield
        finally:
            LOG.info("Deleting previously created volume '%s'...",
                     volume.display_name)
            cn_client.delete_volume(volume.id)

    @contextlib.contextmanager
    def create_instance(self, nv_client, instance_info):
        LOG.info("Creating instance '%s'...", instance_info['name'])
        instance = nv_client.nova_client.servers.create(**instance_info)
        nv_client.wait_for_status(instance.id, nv_client.get_status, 'active',
                                  timeout=300)
        try:
            yield
        finally:
            LOG.info("Deleting previously created instance '%s'...",
                     instance.name)
            nv_client.nova_client.servers.delete(instance.id)
            self.wait_for_instance_to_be_deleted(nv_client=nv_client,
                                                 instance=instance)

    @staticmethod
    def wait_for_instance_to_be_deleted(nv_client, instance):
        retryer = retrying.Retry(max_time=300,
                                 retry_on_return_value=True,
                                 return_value=instance,
                                 expected_exceptions=[nova_exc.NotFound],
                                 retry_message="Instance still exists")
        try:
            with proxy_client.expect_exception(nova_exc.NotFound):
                retryer.run(nv_client.nova_client.servers.get, instance.id)
        except nova_exc.NotFound:
            LOG.info("Instance '%s' has been successfully deleted.",
                     instance.name)

    def run(self, **kwargs):
        """Check write access to cloud."""

        ks_client = keystone.KeystoneIdentity(config=self.cloud.cloud_config,
                                              cloud=self.dst_cloud)
        nt_client = neutron.NeutronNetwork(config=self.cloud.cloud_config,
                                           cloud=self.dst_cloud)
        gl_client = glance_image.GlanceImage(config=self.cloud.cloud_config,
                                             cloud=self.dst_cloud)
        cn_client = cinder.CinderStorage(config=self.cloud.cloud_config,
                                         cloud=self.dst_cloud)

        adm_tenant_name = self.cloud.cloud_config.cloud.tenant
        adm_tenant_id = ks_client.get_tenant_id_by_name(adm_tenant_name)

        unique = str(int(time.time()))
        tenant_name = 'tenant_%s' % unique

        flavor = {
            'name': 'flavor_%s' % unique,
            'is_public': True,
            'ram': 1,
            'vcpus': 1,
            'disk': 1,
        }

        image_info = {
            'name': 'image_%s' % unique,
            'container_format': 'bare',
            'disk_format': 'qcow2',
            'is_public': True,
            'protected': False,
            'owner': adm_tenant_id,
            'size': 4,
            'properties': {'user_name': 'test_user_name'},
            'data': 'test'
        }

        shared_network_info = {
            'network': {
                'tenant_id': adm_tenant_id,
                'admin_state_up': True,
                'shared': True,
                'name': 'shared_net_%s' % unique,
                'router:external': True
            }
        }

        try:
            with self.create_tenant(ks_client, tenant_name) as tenant, \
                    self.create_image(gl_client, image_info) as image_id, \
                    self.create_network(nt_client, shared_network_info):

                private_network_info = {
                    'network': {
                        'tenant_id': tenant.id,
                        'name': 'private_net_%s' % unique,
                    }
                }

                volume_info = {
                    'size': 1,
                    'display_name': 'volume_%s' % unique,
                    'project_id': tenant.id
                }

                with self.create_network(nt_client, private_network_info) as \
                        private_network_id, \
                        self.create_volume(cn_client, volume_info):

                    subnet_info = {
                        'subnet': {
                            'name': 'subnet_%s' % unique,
                            'network_id': private_network_id,
                            'cidr': '192.168.1.0/24',
                            'ip_version': 4,
                            'tenant_id': tenant.id,
                        }
                    }

                    nv_client_config = copy.deepcopy(self.cloud.cloud_config)
                    nv_client_config.cloud.tenant = tenant.name

                    nv_client = nova_compute.NovaCompute(
                        config=nv_client_config, cloud=self.dst_cloud)

                    with self.create_subnet(nt_client, subnet_info), \
                            self.create_flavor(nv_client, flavor) as flavor_id:

                        instance_info = {
                            'name': 'test_vm_%s' % unique,
                            'image': image_id,
                            'flavor': flavor_id,
                            'nics': [{'net-id': private_network_id}]
                        }

                        with self.create_instance(nv_client, instance_info):
                            pass

        except (ks_exc.ClientException, nova_exc.ClientException,
                cinder_exc.ClientException, glance_exc.ClientException,
                neutron_exc.NeutronClientException) as e:
            raise exception.AbortMigrationError(
                "Destination cloud verification failed: {error_message}",
                error_message=e.message)
