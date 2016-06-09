# Copyright (c) 2016 Mirantis Inc.
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

import collections

from generator import generator, generate
from nose.plugins.attrib import attr

import cloudferry_devlab.tests.config as config
from cloudferry_devlab.tests import functional_test
from cloudferry_devlab.tests import test_exceptions


@generator
class GlanceMigrationTests(functional_test.FunctionalTest):
    """Test Case class which includes glance images migration cases."""

    def setUp(self):
        super(GlanceMigrationTests, self).setUp()
        self.dst_images = [x for x in self.dst_cloud.glanceclient.images.list()
                           ]

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_image_members(self):
        """Validate image members were migrated with correct names.
        """

        def member_list_collector(_images, client, auth_client):
            _members = []
            for img in _images:
                members = client.image_members.list(img.id)
                if not members:
                    continue
                mbr_list = []
                for mem in members:
                    mem_name = auth_client.tenants.find(id=mem.member_id).name
                    mbr_list.append(mem_name)
                _members.append({img.name: sorted(mbr_list)})
            return sorted(_members)

        src_images = [img for img in self.src_cloud.glanceclient.images.list()
                      if img.name not in config.images_not_included_in_filter]
        dst_images = [img for img in self.dst_cloud.glanceclient.images.list(
            is_public=None)]

        src_members = member_list_collector(src_images,
                                            self.src_cloud.glanceclient,
                                            self.src_cloud.keystoneclient)
        dst_members = member_list_collector(dst_images,
                                            self.dst_cloud.glanceclient,
                                            self.dst_cloud.keystoneclient)
        missed_members = [member for member in src_members if member
                          not in dst_members]
        if missed_members:
            self.fail("Members: %s not in the DST list of image members."
                      % missed_members)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    @attr(migration_engine=['migrate2'])
    @generate('name', 'disk_format', 'container_format', 'size', 'checksum',
              'status', 'deleted', 'min_disk', 'protected', 'min_ram',
              'is_public', 'virtual_size', 'id')
    def test_migrate_glance_images(self, param):
        """Validate images were migrated with correct parameters.

        :param name: image name
        :param disk_format: raw, vhd, vmdk, vdi, iso, qcow2, etc
        :param container_format: bare, ovf, ova, etc
        :param size: image size
        :param checksum: MD5 checksum of the image file data
        :param status: image status
        :param deleted: is image deleted
        :param min_disk: minimum disk size
        :param protected: is image protected
        :param min_ram: ram required for image
        :param is_public: is image public
        :param virtual_size: size of the virtual disk
        :param id: image id"""
        src_images = self.filter_images({'delete_on_dst': True})
        src_images = self.filtering_utils.filter_images(src_images)[0]

        self.validate_resource_parameter_in_dst(src_images, self.dst_images,
                                                resource_name='image',
                                                parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    @attr(migration_engine=['migrate2'])
    def test_migrate_deleted_glance_images_only_once(self):
        """Validate deleted and broken images were migrated to dst only once.

        Scenario:
            1. Get deleted and broken image's ids from src
            2. Get all images from dst
            3. Verify each deleted and broken image has been restored once
        """
        src_vms = self.src_cloud.novaclient.servers.list(
            search_opts={'all_tenants': True})
        src_img_ids = [i.id for i in self.src_cloud.glanceclient.images.list()]
        # getting images, from which vms were spawned, but which do not exist
        # in the glance
        to_restore_img_ids = []
        for vm in src_vms:
            if vm.image and vm.image['id'] not in src_img_ids:
                to_restore_img_ids.append(vm.image['id'])
        # getting 'broken' images (which exist in the glance, but deleted in
        # storage)
        all_images = self.migration_utils.get_all_images_from_config()
        broken_images = [i['name'] for i in all_images if i.get('broken')]
        src_images = self.src_cloud.glanceclient.images.list()
        to_restore_img_ids.extend([image.id for image in src_images
                                   if image.name in broken_images])

        restored_dst_images = collections.defaultdict(int)
        for deleted_img_id in set(to_restore_img_ids):
            for dst_image in self.dst_images:
                if dst_image.name and deleted_img_id in dst_image.name:
                    restored_dst_images[deleted_img_id] += 1
        msg = 'Image "%s" was re-created %s times. '
        error_msg = ''
        for image in restored_dst_images:
            if restored_dst_images[image] > 1:
                error_msg += msg % (image, restored_dst_images[image])
        if error_msg:
            self.fail(error_msg)

    @attr(migrated_tenant=['tenant1', 'tenant2'])
    def test_migrate_glance_image_belongs_to_deleted_tenant(self):
        """Validate images from deleted tenants were migrated to dst admin
        tenant."""
        src_image_names = []

        def get_image_by_name(image_list, img_name):
            for image in image_list:
                if image.name == img_name:
                    return image

        for tenant in config.tenants:
            if tenant.get('deleted') and tenant.get('images'):
                src_image_names.extend([image['name'] for image in
                                        tenant['images']])

        dst_image_names = [image.name for image in self.dst_images]
        dst_tenant_id = self.dst_cloud.get_tenant_id(self.dst_cloud.tenant)

        missed_images = []
        wrong_image_members = []
        for image_name in src_image_names:
            if image_name not in dst_image_names:
                missed_images.append(image_name)
            image = get_image_by_name(self.dst_images, image_name)
            if image.owner != dst_tenant_id:
                wrong_image_members.append(image.owner)
        if missed_images:
            msg = 'Images {0} is not in DST image list: {1}'.format(
                missed_images, dst_image_names)
            if wrong_image_members:
                msg += '\nand\nImage owners on dst is {0} instead of {1}'\
                    .format(wrong_image_members, dst_tenant_id)
            self.fail(msg)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    @attr(migration_engine=['migrate2'])
    def test_glance_images_not_in_filter_did_not_migrate(self):
        """Validate images not in filter weren't migrated."""
        migrated_images_not_in_filter = [image for image in
                                         config.images_not_included_in_filter
                                         if image in self.dst_images]

        if migrated_images_not_in_filter:
            self.fail('Image migrated despite that it was not included '
                      'in filter, Images info: \n{}'.format(
                        migrated_images_not_in_filter))

    @attr(migration_engine=['migrate2'])
    def test_glance_image_deleted_and_migrated_second_time_with_new_id(self):
        """Validate deleted images were migrated second time with new id."""
        src_images = []
        for image in config.images:
            if image.get('delete_on_dst'):
                src_images.append(image)

        images_with_same_id = []
        for src_image in src_images:
            src_image = self.src_cloud.glanceclient.images.get(
                src_image['id'])
            images_with_same_id.extend([dst_image.name for dst_image
                                        in self.dst_images
                                        if src_image.name == dst_image.name and
                                        src_image.id == dst_image.id])

        if images_with_same_id:
            msg = "The images with name {src_image_name} have the "\
                  "same ID on dst - must be different for this image,"\
                  "because this image was migrated and deleted on dst. "\
                  "On the next migration must be generated new ID"
            self.fail(msg=msg.format(src_image_name=images_with_same_id))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_not_valid_images_did_not_migrate(self):
        """Validate images with invalid statuses weren't migrated.
        Invalid images have 'broken': True value in :mod:`config.py`
        """
        all_images = self.migration_utils.get_all_images_from_config()
        images = [image['name'] for image in all_images if image.get('broken')]
        migrated_images = []
        for image in images:
            try:
                self.dst_cloud.get_image_id(image)
                migrated_images.append(image)
            except test_exceptions.NotFound:
                pass
        if migrated_images:
            self.fail('Not valid images %s migrated')
