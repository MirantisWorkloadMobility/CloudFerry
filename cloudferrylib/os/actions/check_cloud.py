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
import time

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl
from cloudferrylib.os.identity.keystone import KeystoneIdentity
from cloudferrylib.os.compute.nova_compute import NovaCompute
from cloudferrylib.os.network.neutron import NeutronNetwork
from cloudferrylib.os.image.glance_image import GlanceImage
from cloudferrylib.os.storage.cinder_storage import CinderStorage
from keystoneclient.openstack.common.apiclient import exceptions as ks_exc
from novaclient import exceptions as nova_exc
from glanceclient import exc as glance_exc
from neutronclient.common import exceptions as neutron_exc
from cinderclient import exceptions as cinder_exc
from cloudferrylib.base import exception

LOG = utl.get_log(__name__)


class CheckCloud(action.Action):
    def __init__(self, init, cloud=None):
        super(CheckCloud, self).__init__(init, cloud)

    @contextlib.contextmanager
    def create_tenant(self, ks_client, tenant_name):
        LOG.info("Creating %s tenant.", tenant_name)
        tenant_id = ks_client.create_tenant(tenant_name)
        try:
            yield tenant_id
        finally:
            LOG.info("Deleting previously created tenant.")
            ks_client.delete_tenant(tenant_id)

    @contextlib.contextmanager
    def create_flavor(self, nv_client, flavor):
        LOG.info("Creating %s flavor.", flavor['name'])
        flavor_id = nv_client.create_flavor(**flavor)
        try:
            yield flavor_id
        finally:
            LOG.info("Deleting previously created flavor.")
            nv_client.delete_flavor(flavor_id)

    @contextlib.contextmanager
    def create_network(self, nt_client, network):
        LOG.info("Creating %s network.", network['network']['name'])
        net_id = \
            nt_client.neutron_client.create_network(network)['network']['id']
        try:
            yield net_id
        finally:
            LOG.info("Deleting %s network.", network['network']['name'])
            nt_client.neutron_client.delete_network(net_id)

    @contextlib.contextmanager
    def create_subnet(self, nt_client, subnet_info):
        LOG.info("Creating %s subnet.", subnet_info['subnet']['name'])
        subnet_id = \
            nt_client.neutron_client.create_subnet(subnet_info)['subnet']['id']
        try:
            yield
        finally:
            LOG.info("Deleting %s subnet", subnet_info['subnet']['name'])
            nt_client.neutron_client.delete_subnet(subnet_id)

    @contextlib.contextmanager
    def create_image(self, gl_client, image_info):
        LOG.info("Creating %s image.", image_info['name'])
        image = gl_client.create_image(**image_info)
        try:
            yield image
        finally:
            LOG.info("Deleting %s image.", image_info['name'])
            gl_client.delete_image(image.id)

    @contextlib.contextmanager
    def create_volume(self, cn_client, volume_info):
        LOG.info("Creating %s volume.", volume_info['display_name'])
        volume = cn_client.create_volume(**volume_info)
        try:
            yield
        finally:
            LOG.info("Deleting %s volume.", volume_info['display_name'])
            cn_client.delete_volume(volume.id)

    @contextlib.contextmanager
    def create_instance(self, nv_client, instance_info):
        LOG.info("Creating %s instance.", instance_info['name'])
        instance_id = nv_client.nova_client.servers.create(**instance_info)
        nv_client.wait_for_status(instance_id, nv_client.get_status, 'active',
                                  timeout=300)
        try:
            yield
        finally:
            LOG.info("Deleting instance.")
            nv_client.nova_client.servers.delete(instance_id)
            self.wait_for_instance_to_be_deleted(nv_client=nv_client,
                                                 instance_id=instance_id,
                                                 timeout=300)

    @classmethod
    def wait_for_instance_to_be_deleted(cls, nv_client, instance_id,
                                        timeout=60):
        try:
            delay = 1
            while timeout > delay:
                nv_client.nova_client.servers.get(instance_id)
                LOG.info("Instance still exist, waiting %s sec", delay)
                time.sleep(delay)
                delay *= 2
        except nova_exc.NotFound:
            LOG.info("Instance successfuly deleted.")

    def run(self, **kwargs):
        """Check write access to cloud."""

        ks_client = KeystoneIdentity(config=self.cloud.cloud_config,
                                     cloud=self.dst_cloud)
        nv_client = NovaCompute(config=self.cloud.cloud_config,
                                cloud=self.dst_cloud)
        nt_client = NeutronNetwork(config=self.cloud.cloud_config,
                                   cloud=self.dst_cloud)
        gl_client = GlanceImage(config=self.cloud.cloud_config,
                                cloud=self.dst_cloud)
        cn_client = CinderStorage(config=self.cloud.cloud_config,
                                  cloud=self.dst_cloud)

        adm_tenant_name = self.cloud.cloud_config.cloud.tenant
        adm_tenant_id = ks_client.get_tenant_id_by_name(adm_tenant_name)

        err_message = 'Failed to create object in the cloud'
        unique = str(int(time.time()))
        tenant_name = 'tenant_%s' % unique
        flavor = {
            'name': 'flavor_%s' % unique,
            'is_public': True,
            'ram': '1',
            'vcpus': '1',
            'disk': '1',
            'ephemeral': '1',
            'swap': '1',
            'rxtx_factor': '1'
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

        private_network_info = {
            'network': {
                'tenant_id': '',
                'admin_state_up': False,
                'shared': False,
                'name': 'private_net_%s' % unique,
                'router:external': False
            }
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

        subnet_info = {
            'subnet': {
                'name': 'subnet_%s' % unique,
                'network_id': '',
                'cidr': '192.168.1.0/24',
                'ip_version': 4,
                'tenant_id': '',
            }
        }

        volume_info = {
            'availability_zone': 'nova',
            'display_description': None,
            'size': 1,
            'display_name': 'volume_%s' % unique,
            'volume_type': None
        }

        try:
            with self.create_tenant(ks_client, tenant_name) as tenant_id, \
                    self.create_flavor(nv_client, flavor) as flavor_id, \
                    self.create_image(gl_client, image_info) as image:

                private_network_info['tenant_id'] = tenant_id
                subnet_info['subnet']['tenant_id'] = tenant_id

                with self.create_network(nt_client, private_network_info) as\
                        private_network_id, \
                        self.create_network(nt_client, shared_network_info):

                    subnet_info['subnet']['network_id'] = private_network_id
                    nics = [{'net-id': private_network_id}]

                    with self.create_subnet(nt_client, subnet_info), \
                            self.create_volume(cn_client, volume_info):
                        instance_info = {
                            'name': 'test_vm_%s' % unique,
                            'image': image.id,
                            'flavor': flavor_id,
                            'nics': nics
                        }
                        with self.create_instance(nv_client, instance_info):
                            pass

        except (ks_exc.ClientException, nova_exc.ClientException,
                cinder_exc.ClientException, glance_exc.ClientException,
                neutron_exc.NeutronClientException):
            LOG.error(err_message)
            raise exception.AbortMigrationError(err_message)
