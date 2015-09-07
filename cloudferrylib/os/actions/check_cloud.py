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

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl
from keystoneclient.openstack.common.apiclient import exceptions as keystone_exc
from novaclient import exceptions as nova_exc
from cloudferrylib.base import exception

LOG = utl.get_log(__name__)


class CheckCloud(action.Action):
    def __init__(self, init, cloud=None):
        super(CheckCloud, self).__init__(init, cloud)

    def run(self, **kwargs):
        """Check write access to cloud."""
        ident_resource = self.dst_cloud.resources[utl.IDENTITY_RESOURCE]
        image_res = self.cloud.resources[utl.IMAGE_RESOURCE]
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        volume_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        net_resource = self.cloud.resources[utl.NETWORK_RESOURCE]
        admin_tenant_name = self.cloud.cloud_config.cloud.tenant
        admin_tenant_id = ident_resource.get_tenant_id_by_name(admin_tenant_name)
        tenant_name = 'test_name'
        flavor_id = 'c0c0c0c0'
        err_message = 'Failed to create object in the cloud'
        tenant = [{
            'meta': {},
            'tenant': {
                'name': tenant_name,
                'description': None
            }
        }]
        flavor = {
            flavor_id: {
                'flavor': {
                    'name': 'test_flavor',
                    'is_public': True,
                    'ram': '1',
                    'vcpus': '1',
                    'disk': '1',
                    'ephemeral': '1',
                    'swap': '1',
                    'rxtx_factor': '1'
                },
                'meta': {
                    'id': flavor_id
                }
            }
        }
        try:
            ident_resource._deploy_tenants(tenant)
            tenant_id = ident_resource.get_tenant_id_by_name(tenant_name)
            compute_resource._deploy_flavors(flavor, None)
        except (keystone_exc.ClientException,
                nova_exc.ClientException) as e:
            LOG.error(err_message)
            raise exception.AbortMigrationError(err_message)
        migrate_image = image_res.create_image(
            name='test_image',
            container_format='bare',
            disk_format='qcow2',
            is_public=True,
            protected=False,
            owner=admin_tenant_id,
            size=4,
            properties={'user_name': 'test_user_name'},
            data='test'
        )
        info = {
            'instances': {
                'a0a0a0a': {
                    'instance': {
                        'id': 'a0a0a0a0',
                        'name': 'test_vm',
                        'image_id': migrate_image.id,
                        'flavor_id': flavor_id,
                        'key_name': '1',
                        'nics': None,
                        'user_id': '1',
                        'boot_mode': utl.BOOT_FROM_IMAGE,
                        'availability_zone': 'nova',
                        'tenant_name': admin_tenant_name
                    }
                }
            },
            'volumes': {
                'd0d0d0d0': {
                    'volume': {
                        'availability_zone': 'nova',
                        'display_description': None,
                        'id': 'd0d0d0d0',
                        'size': 1,
                        'display_name': 'test_volume',
                        'bootable': False,
                        'volume_type': None
                    },
                    'meta': {},
                }
            }
        }
        vol_new_ids = volume_resource.deploy_volumes(info)
        volume_resource.cinder_client.volumes.delete(vol_new_ids.keys()[0])
        network_info = {
            'network': {
                'tenant_id': admin_tenant_id,
                'admin_state_up': True,
                'shared': True,
                'name': 'test_net',
                'router:external': True
            }
        }
        new_net_id = net_resource.neutron_client.create_network(
            network_info)['network']['id']
        net_resource.neutron_client.delete_network(new_net_id)
        vm_new_ids = compute_resource._deploy_instances(info)
        if not vm_new_ids or not vol_new_ids or not migrate_image or not new_net_id:
            LOG.error(err_message)
            raise exception.AbortMigrationError(err_message)
        compute_resource.nova_client.servers.delete(vm_new_ids.keys()[0])
        image_res.glance_client.images.delete(migrate_image.id)
        compute_resource.nova_client.flavors.delete(flavor_id)
        ident_resource.keystone_client.tenants.delete(tenant_id)
