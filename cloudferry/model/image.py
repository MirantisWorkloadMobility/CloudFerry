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
from cloudferry import model
from cloudferry.model import identity


@model.type_alias('image_members')
class ImageMember(model.Model):
    object_id = model.PrimaryKey()
    image = model.Dependency('cloudferry.model.image.Image')
    member = model.Dependency('cloudferry.model.identity.Tenant')
    can_share = model.Boolean(missing=False)

    @staticmethod
    def make_uuid(image, tenant):
        return '{0}:{1}'.format(image.object_id.id, tenant.object_id.id)

    def equals(self, other):
        # pylint: disable=no-member
        if super(ImageMember, self).equals(other):
            return True
        return self.image.equals(other.image) and \
            self.member.equals(other.member) and \
            self.can_share == other.can_share


@model.type_alias('images')
class Image(model.Model):
    object_id = model.PrimaryKey()
    name = model.String(allow_none=True)
    tenant = model.Dependency(identity.Tenant)
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

    def equals(self, other):
        # pylint: disable=no-member
        if super(Image, self).equals(other):
            return True
        # TODO: consider comparing properties
        return self.tenant.equals(other.tenant) and \
            self.name == other.name and \
            self.checksum == other.checksum and \
            self.size == other.size and \
            self.is_public == other.is_public and \
            self.container_format == other.container_format and \
            self.disk_format == other.disk_format
