# Copyright 2016 Mirantis Inc.
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
import logging

from glanceclient import exc as glance_exc

from cloudferry.lib.os import clients
from cloudferry.lib.os.discovery import keystone
from cloudferry.lib.os.discovery import model

LOG = logging.getLogger(__name__)


@model.type_alias('image_members')
class ImageMember(model.Model):
    class Schema(model.Schema):
        object_id = model.PrimaryKey()
        image = model.Dependency('cloudferry.lib.os.discovery.glance.Image')
        member = model.Dependency(
            'cloudferry.lib.os.discovery.keystone.Tenant')
        can_share = model.Boolean(missing=False)

    @classmethod
    def load_from_cloud(cls, cloud, data, overrides=None):
        return cls.make(cloud, data.image_id, data.member_id)

    @classmethod
    def load_missing(cls, cloud, object_id):
        image_id, member_id = object_id.id.split(':')
        return cls.make(cls, image_id, member_id)

    @classmethod
    def make(cls, cloud, image_id, member_id, can_share=False):
        return super(ImageMember, cls).load_from_cloud(cloud, {
            'object_id': '{0}:{1}'.format(image_id, member_id),
            'image': image_id,
            'member': member_id,
            'can_share': can_share,
        })

    def equals(self, other):
        # pylint: disable=no-member
        return self.image.equals(other.image) \
               and self.member.equals(other.member) \
               and self.can_share == other.can_share


@model.type_alias('images')
class Image(model.Model):
    class Schema(model.Schema):
        object_id = model.PrimaryKey('id')
        name = model.String(allow_none=True)
        tenant = model.Dependency(keystone.Tenant)
        checksum = model.String(allow_none=True)
        size = model.Integer()
        virtual_size = model.Integer(allow_none=True, missing=None)
        is_public = model.Boolean()
        protected = model.Boolean()
        container_format = model.String(missing='qcow2')
        disk_format = model.String(missing='bare')
        min_disk = model.Integer(required=True)
        min_ram = model.Integer(required=True)
        properties = model.Dict()
        members = model.Reference(ImageMember, many=True, missing=list)
        status = model.String()

        FIELD_MAPPING = {
            'tenant': 'owner',
        }

    @classmethod
    def load_missing(cls, cloud, object_id):
        image_client = clients.image_client(cloud)
        raw_image = image_client.images.get(object_id.id)
        image = Image.load_from_cloud(cloud, raw_image)
        try:
            for member in image_client.image_members.list(image=raw_image):
                image.members.append(
                    ImageMember.load_from_cloud(cloud, member))
        except glance_exc.HTTPNotFound:
            pass
        return image

    @classmethod
    def discover(cls, cloud):
        image_client = clients.image_client(cloud)
        with model.Session() as session:
            for raw_image in image_client.images.list(
                    filters={'is_public': None, 'status': 'active'}):
                try:
                    image = Image.load_from_cloud(cloud, raw_image)
                    session.store(image)
                    members_list = image_client.image_members.list(
                        image=raw_image)
                    for raw_member in members_list:
                        member = ImageMember.load_from_cloud(cloud, raw_member)
                        session.store(member)
                        image.members.append(member)
                except model.ValidationError as e:
                    LOG.warning('Invalid image %s: %s', raw_image.id, e)

    def equals(self, other):
        # pylint: disable=no-member
        # TODO: consider comparing properties
        return self.tenant.equals(other.tenant) and \
            self.name == other.name and \
            self.checksum == other.checksum and \
            self.size == other.size and \
            self.is_public == other.is_public and \
            self.container_format == other.container_format and \
            self.disk_format == other.disk_format
