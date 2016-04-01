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


import copy

import mock

from cinderclient import exceptions as cinder_exc
from glanceclient import exc as glance_exc
from keystoneclient import exceptions as keystone_exc
from novaclient import exceptions as nova_exc
from oslotest import mockpatch

from cloudferrylib.base import exception
from cloudferrylib.os.actions import check_filter
from tests import test


class CheckFilterTestCase(test.TestCase):
    def setUp(self):
        super(CheckFilterTestCase, self).setUp()

        fake_utils = mock.Mock()
        utils_patch = mockpatch.Patch(
            "cloudferrylib.os.actions.check_filter.utils", new=fake_utils)
        self.useFixture(utils_patch)

        self.src_image = mock.Mock()
        self.src_compute = mock.Mock()
        self.src_storage = mock.Mock()
        self.src_identity = mock.Mock()

        fake_src_cloud = mock.Mock()
        fake_src_cloud.resources = {
            fake_utils.IMAGE_RESOURCE: self.src_image,
            fake_utils.COMPUTE_RESOURCE: self.src_compute,
            fake_utils.STORAGE_RESOURCE: self.src_storage,
            fake_utils.IDENTITY_RESOURCE: self.src_identity
        }

        fake_config = mock.Mock()
        fake_config.migrate.migrate_whole_cloud = False
        fake_config.migrate.filter_path = '/fake/filter_path.yaml'

        fake_init = {'src_cloud': fake_src_cloud, 'cfg': fake_config}
        self.fake_action = check_filter.CheckFilter(fake_init,
                                                    cloud='src_cloud')

        self.opts = dict(search_opts_tenant={}, search_opts={},
                         search_opts_vol={}, search_opts_img={})

    @mock.patch("cloudferrylib.os.actions.check_filter.utils")
    def test_no_filter_file(self, fake_utils):
        fake_utils.check_file.return_value = False

        self.assertRaises(exception.AbortMigrationError, self.fake_action.run)

    @mock.patch("cloudferrylib.os.actions.check_filter.utils")
    def test_empty_filter(self, fake_utils):
        fake_utils.read_yaml_file.return_value = {}

        self.assertRaises(exception.AbortMigrationError, self.fake_action.run)

    def test_no_get_filter_action_before(self):
        self.assertRaises(exception.AbortMigrationError, self.fake_action.run)

    def test_filter_non_existing_tenant(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['non_existing_tenant_id']}
        self.src_identity.keystone_client.tenants.get.side_effect = (
            keystone_exc.NotFound)

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)

    def test_filter_existing_tenant(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}

        self.fake_action.run(**opts)

        self.src_identity.keystone_client.tenants.get.assert_called_once_with(
            'existing_tenant_id')

    def test_filter_no_tenants(self):
        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **self.opts)

    def test_filter_several_tenants(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {
            'tenant_id': ['existing_tenant_id', 'one_more_existing_tenant_id']}

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)

    def test_filter_existing_instance(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts'] = {'id': ['existing_instance_id']}

        self.fake_action.run(**opts)

        self.src_compute.nova_client.servers.get.assert_called_once_with(
            'existing_instance_id')

    def test_filter_non_existing_instance(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts'] = {'id': ['non_existing_instance_id']}

        self.src_compute.nova_client.servers.get.side_effect = (
            nova_exc.NotFound(404))

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)

    def test_filter_existing_volume(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_vol'] = {'volumes_list': ['existing_volume_id']}

        self.fake_action.run(**opts)

        self.src_storage.cinder_client.volumes.get.assert_called_once_with(
            'existing_volume_id')

    def test_filter_non_existing_volume(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_vol'] = {'volumes_list': ['non_existing_volume_id']}

        self.src_storage.cinder_client.volumes.get.side_effect = (
            cinder_exc.NotFound(404))

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)

    def test_filter_valid_date(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_vol'] = {'date': "1991-08-24 00:00:00"}

        self.fake_action.run(**opts)

    def test_filter_invalid_date(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_vol'] = {'date': "03-16-2014"}

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)

    def test_filter_existing_image(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_img'] = {'exclude_images_list': ['existing_img_id']}

        self.fake_action.run(**opts)

        self.src_image.glance_client.images.get.assert_called_once_with(
            'existing_img_id')

    def test_filter_non_existing_image(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_img'] = {'images_list': ['non_existing_image_id']}

        self.src_image.glance_client.images.get.side_effect = (
            glance_exc.NotFound)

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)

    def test_image_conflict_options(self):
        opts = copy.deepcopy(self.opts)
        opts['search_opts_tenant'] = {'tenant_id': ['existing_tenant_id']}
        opts['search_opts_img'] = {'exclude_images_list': ['existing_img_id'],
                                   'images_list': ['another_existing_img_id']}

        self.assertRaises(exception.AbortMigrationError,
                          self.fake_action.run, **opts)
