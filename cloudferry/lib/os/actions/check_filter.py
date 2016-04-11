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


import datetime
import yaml

from cinderclient import exceptions as cinder_exc
from glanceclient import exc as glance_exc
from keystoneclient import exceptions as keystone_exc
from novaclient import exceptions as nova_exc

from cloudferry.lib.base.action import action
from cloudferry.lib.base import exception
from cloudferry.lib.os.storage import filters as cinder_filters
from cloudferry.lib.utils import log
from cloudferry.lib.utils import proxy_client
from cloudferry.lib.utils import utils


LOG = log.getLogger(__name__)


NOT_FOUND_EXC_LIST = (nova_exc.NotFound, cinder_exc.NotFound,
                      glance_exc.NotFound, keystone_exc.NotFound)


class CheckFilter(action.Action):

    """
    Check filter config file.

    Check and make sure all entries are present and valid on the source cloud.

    Required configuration options:
        [migrate]
        migrate_whole_cloud = False
        filter_path = <path_to_filter_config_file>

    Scenario:
        preparation:
            - pre_migration_test:
                -act_check_filter: True

    Required tasks:
        GetFilter
    Dependent tasks:
        None
    """

    def run(self, **kwargs):

        if self.cfg.migrate.migrate_whole_cloud:
            LOG.info("Whole cloud migration is enabled. Ignore filtering...")
            return

        filter_path = self.cfg.migrate.filter_path

        if not utils.check_file(filter_path):
            raise exception.AbortMigrationError(
                "Filter file '%s' has not been found. Please check filter file"
                " path in the CloudFerry configuration file." % filter_path)

        if not utils.read_yaml_file(filter_path):
            raise exception.AbortMigrationError("Filter file '%s' is empty." %
                                                filter_path)

        try:
            tenant_opts = kwargs['search_opts_tenant']
            instance_opts = kwargs['search_opts']
            volume_opts = kwargs['search_opts_vol']
            image_opts = kwargs['search_opts_img']
        except KeyError:
            raise exception.AbortMigrationError(
                "Action 'act_get_filter' should be specified prior this action"
                " in the scenario file. Aborting migration...")

        tenant = Tenant(self.cloud, tenant_opts)
        instance = Instance(self.cloud, instance_opts)
        volume = Volume(self.cloud, volume_opts)
        image = Image(self.cloud, image_opts)

        invalid_data = {}
        for filter_object in [tenant, instance, volume, image]:
            invalid_data.update(filter_object.check())

        # Filter only non-empty values
        invalid_data = {k: v for k, v in invalid_data.iteritems() if v}

        if invalid_data:
            msg = "\n\nInvalid Filter Data:\n\n%s" % yaml.dump(invalid_data)
            LOG.critical(msg)
            raise exception.AbortMigrationError(
                "There is a number of invalid data specified in the filter "
                "file '%s', so migration process can not be continued. Please "
                "update your filter config file and try again. %s" %
                (filter_path, msg))


class BaseFilteredObject(object):
    def __init__(self, name, get_method, ids_list):
        self.name = name
        self.get_method = get_method
        self.ids_list = ids_list or []

    def check(self):
        non_existing_ids_list = []

        for obj_id in self.ids_list:
            LOG.debug("Filtered %s ID: '%s'", self.name, obj_id)
            try:
                with proxy_client.expect_exception(NOT_FOUND_EXC_LIST):
                    obj = self.get_method(obj_id)
                if obj:
                    LOG.debug("Filter config check: %s ID '%s' is OK",
                              self.name, obj_id)
            except NOT_FOUND_EXC_LIST:
                LOG.error("Filter config check: %s ID '%s' is not present on "
                          "the source cloud.", self.name, obj_id)
                non_existing_ids_list.append(obj_id)

        return {"Non-existing %s IDs list" % self.name: non_existing_ids_list}


class Tenant(BaseFilteredObject):
    def __init__(self, cloud, opts):
        resource = cloud.resources[utils.IDENTITY_RESOURCE]
        get_method = resource.keystone_client.tenants.get
        opts = opts or {}

        super(Tenant, self).__init__(name='Tenant',
                                     get_method=get_method,
                                     ids_list=opts.get('tenant_id'))

    def check_tenants_amount(self):
        if len(self.ids_list) > 1:
            raise exception.AbortMigrationError(
                'More than one tenant in filter config file is not supported. '
                'Aborting migration...')
        elif len(self.ids_list) < 1:
            raise exception.AbortMigrationError(
                "Tenant ID in not specified in the filter config file. Please"
                " either specify it or use 'migrate_whole_cloud = True' in the"
                " main config file for the whole cloud migration.")

    def check(self):
        self.check_tenants_amount()
        return super(Tenant, self).check()


class Instance(BaseFilteredObject):
    def __init__(self, cloud, opts):
        resource = cloud.resources[utils.COMPUTE_RESOURCE]
        get_method = resource.nova_client.servers.get
        opts = opts or {}

        super(Instance, self).__init__(name='Instance',
                                       get_method=get_method,
                                       ids_list=opts.get('id'))


class Volume(BaseFilteredObject):
    def __init__(self, cloud, opts):
        resource = cloud.resources[utils.STORAGE_RESOURCE]
        get_method = resource.cinder_client.volumes.get
        self.opts = opts or {}

        super(Volume, self).__init__(name='Volume',
                                     get_method=get_method,
                                     ids_list=self.opts.get('volumes_list'))

    def check_invalid_date(self):
        volumes_date = self.opts.get('date')

        if not volumes_date:
            return {}

        if isinstance(volumes_date, datetime.datetime):
            LOG.debug("Filtered datetime volume date: '%s'", str(volumes_date))
        else:
            try:
                volumes_date = datetime.datetime.strptime(
                    volumes_date, cinder_filters.DATETIME_FMT)
                LOG.debug("Filtered str volume date: '%s'", str(volumes_date))
            except ValueError:
                LOG.error("Filter config check: invalid volume date format: "
                          "'%s'", volumes_date)

                return {"Invalid Volume Date": [volumes_date]}

        return {}

    def check(self):
        invalid_volume_data = super(Volume, self).check()

        invalid_volume_data.update(self.check_invalid_date())

        return invalid_volume_data


class Image(BaseFilteredObject):
    def __init__(self, cloud, opts):
        resource = cloud.resources[utils.IMAGE_RESOURCE]
        get_method = resource.glance_client.images.get
        self.opts = opts or {}

        ids_list = (self.opts.get('images_list') or
                    self.opts.get('exclude_images_list'))

        super(Image, self).__init__(name='Image',
                                    get_method=get_method,
                                    ids_list=ids_list)

    def check_conflict(self):
        if not self.opts:
            return

        if (self.opts.get('images_list') and
                self.opts.get('exclude_images_list')):
            raise exception.AbortMigrationError(
                "Options 'images_list' and 'exclude_images_list' can not be "
                "specified together at the same time in the filter file. "
                "Should be only one of them. Aborting migration...")

    def check(self):
        self.check_conflict()
        return super(Image, self).check()
