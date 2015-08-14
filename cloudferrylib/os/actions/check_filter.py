# Copyright (c) 2015 Mirantis Inc.
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


from glanceclient import exc as glance_exc
from keystoneclient import exceptions as keystone_exc
from novaclient import exceptions as nova_exc
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl

LOG = utl.get_log(__name__)


class CheckFilter(action.Action):
    def run(self, **kwargs):
        """Check filter file and make sure all entries are present in source cloud.

        """
        search_opts = kwargs.get('search_opts', {})
        search_opts_img = kwargs.get('search_opts_img', {})
        search_opts_tenant = kwargs.get('search_opts_tenant', {})
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        if search_opts_img and search_opts_img.get('images_list'):
            images_list = search_opts_img['images_list']
            for img_id in images_list:
                LOG.debug('Filtered image id: {}'.format(img_id))
                try:
                    img = image_resource.glance_client.images.get(img_id)
                    if img:
                        LOG.debug('Filter config check: Image ID {} is OK'.format(img_id))
                except glance_exc.HTTPNotFound as e:
                    LOG.error('Filter config check: Image ID {} is not present in source cloud, '
                              'please update your filter config. Aborting.'.format(img_id))
                    raise e
        ident_resource = self.cloud.resources[utl.IDENTITY_RESOURCE]
        if search_opts_tenant and search_opts_tenant.get('tenant_id'):
            tenants = search_opts_tenant['tenant_id']
            for tenant_id in tenants:
                LOG.debug('Filtered tenant id: {}'.format(tenant_id))
                try:
                    tenant = ident_resource.keystone_client.tenants.find(id=tenant_id)
                    if tenant:
                        LOG.debug('Filter config check: Tenant ID {} is OK'.format(tenant_id))
                except keystone_exc.NotFound as e:
                    LOG.error('Filter config check: Tenant ID {} is not present in source cloud, '
                              'please update your filter config. Aborting.'.format(tenant_id))
                    raise e
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        if search_opts and search_opts.get('id'):
            instances = search_opts['id']
            for instance_id in instances:
                LOG.debug('Filtered instance id: {}'.format(instance_id))
                try:
                    instance = compute_resource.nova_client.servers.get(instance_id)
                    if instance:
                        LOG.debug('Filter config check: Instance ID {} is OK'.format(instance_id))
                except nova_exc.NotFound as e:
                    LOG.error('Filter config check: Instance ID {} is not present in source cloud, '
                              'please update your filter config. Aborting.'.format(instance_id))
                    raise e
