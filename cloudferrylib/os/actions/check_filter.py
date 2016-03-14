"""CheckFilter action."""
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
from cinderclient import exceptions as cinder_exc
from keystoneclient import exceptions as keystone_exc
from novaclient import exceptions as nova_exc
from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.os.storage import filters as cinder_filters
from cloudferrylib.utils import log
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import utils as utl

import datetime

LOG = log.getLogger(__name__)


class CheckFilter(action.Action):

    """CheckFilter class."""

    def run(self, **kwargs):
        """
        Check filter file.

        Check and make sure all entries are present in source cloud.

        """
        search_opts = kwargs.get('search_opts', {})
        self._check_opts_img(kwargs.get('search_opts_img', {}))
        self._check_opts_vol(kwargs.get('search_opts_vol', {}))
        self._check_opts_vol_date(kwargs.get('search_opts_vol', {}))
        self._check_opts_tenant(kwargs.get('search_opts_tenant', {}))

        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        if search_opts and search_opts.get('id'):
            instances = search_opts['id']
            for instance_id in instances:
                LOG.debug('Filtered instance id: %s', instance_id)
                try:
                    with proxy_client.expect_exception(nova_exc.NotFound):
                        instance = \
                            compute_resource.nova_client.servers.get(
                                instance_id)
                    if instance:
                        LOG.debug('Filter config check: Instance ID %s is OK',
                                  instance_id)
                except nova_exc.NotFound:
                    LOG.error('Filter config check: Instance ID %s '
                              'is not present in source cloud, '
                              'please update your filter config. Aborting.',
                              instance_id)
                    raise

    def _check_opts_vol(self, opts):
        if not opts:
            return
        cinder_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        if opts.get('volumes_list'):
            volumes_list = opts['volumes_list']
            for vol_id in volumes_list:
                LOG.debug('Filtered volume id: %s', vol_id)
                try:
                    with proxy_client.expect_exception(cinder_exc.NotFound):
                        vol = cinder_resource.cinder_client.volumes.get(vol_id)
                    if vol:
                        LOG.debug('Filter config check: Volume ID %s is OK',
                                  vol_id)
                except cinder_exc.NotFound:
                    LOG.error('Filter config check: Volume ID %s '
                              'is not present in source cloud, '
                              'please update your filter config. Aborting.',
                              vol_id)
                    raise

    @staticmethod
    def _check_opts_vol_date(opts):
        if opts.get('date'):
            volumes_date = opts['date']
            if isinstance(volumes_date, datetime.datetime):
                LOG.debug('Filtered datetime volume date: %s',
                          str(volumes_date))
            else:
                try:
                    volumes_date = datetime.datetime.strptime(
                        volumes_date, cinder_filters.DATETIME_FMT)
                    LOG.debug('Filtered str volume date: %s',
                              str(volumes_date))
                except ValueError:
                    LOG.error('Filter config check: '
                              'invalid volume date format')
                    raise

    def _check_opts_img(self, opts):
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        if opts and \
                opts.get('images_list') and opts.get('exclude_images_list'):
            raise exception.AbortMigrationError(
                "In the filter config file was specified "
                "'images_list' and 'exclude_images_list'. "
                "Must either specify - 'images_list' or "
                "'exclude_images_list'.")

        if opts and opts.get('images_list'):
            images_list = opts['images_list']
            for img_id in images_list:
                LOG.debug('Filtered image id: %s', img_id)
                try:
                    with proxy_client.expect_exception(glance_exc.NotFound):
                        img = image_resource.glance_client.images.get(img_id)
                    if img:
                        LOG.debug('Filter config check: Image ID %s is OK',
                                  img_id)
                except glance_exc.HTTPNotFound:
                    LOG.error('Filter config check: Image ID %s '
                              'is not present in source cloud, '
                              'please update your filter config. Aborting.',
                              img_id)
                    raise

    def _check_opts_tenant(self, opts):
        ident_resource = self.cloud.resources[utl.IDENTITY_RESOURCE]
        if opts and opts.get('tenant_id'):
            tenants = opts['tenant_id']
            if len(tenants) > 1:
                raise exception.AbortMigrationError(
                    'More than one tenant in tenant filters is not supported.')
            for tenant_id in tenants:
                LOG.debug('Filtered tenant id: %s', tenant_id)
                try:
                    with proxy_client.expect_exception(keystone_exc.NotFound):
                        tenant = ident_resource.keystone_client.tenants.find(
                            id=tenant_id)
                    if tenant:
                        LOG.debug('Filter config check: Tenant ID %s is OK',
                                  tenant_id)
                except keystone_exc.NotFound:
                    LOG.error('Filter config check: Tenant ID %s '
                              'is not present in source cloud, '
                              'please update your filter config. Aborting.',
                              tenant_id)
                    raise
