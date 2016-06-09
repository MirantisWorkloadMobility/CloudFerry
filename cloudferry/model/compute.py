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
from cloudferry.model import image as image_model
from cloudferry.model import storage


@model.type_alias('flavors')
class Flavor(model.Model):
    object_id = model.PrimaryKey()

    def equals(self, other):
        # pylint: disable=no-member
        # TODO: replace with implementation that make sense
        if super(Flavor, self).equals(other):
            return True
        return self.object_id.id == other.object_id.id


class SecurityGroup(model.Model):
    name = model.String(required=True)


class EphemeralDisk(model.Model):
    path = model.String(required=True)
    size = model.Integer(required=True)
    format = model.String(required=True)
    base_path = model.String(required=True, allow_none=True)
    base_size = model.Integer(required=True, allow_none=True)
    base_format = model.String(required=True, allow_none=True)


@model.type_alias('vms')
class Server(model.Model):
    object_id = model.PrimaryKey()
    name = model.String(required=True)
    security_groups = model.Nested(SecurityGroup, many=True, missing=list)
    status = model.String(required=True)
    tenant = model.Dependency(identity.Tenant)
    image = model.Dependency(image_model.Image, allow_none=True)
    image_membership = model.Dependency(image_model.ImageMember,
                                        allow_none=True)
    user_id = model.String(required=True)  # TODO: user reference
    key_name = model.String(required=True, allow_none=True)
    flavor = model.Dependency(Flavor)
    config_drive = model.String(required=True)
    availability_zone = model.String(required=True, allow_none=True)
    host = model.String(required=True)
    hypervisor_hostname = model.String(required=True)
    instance_name = model.String(required=True)
    metadata = model.Dict(missing=dict)
    ephemeral_disks = model.Nested(EphemeralDisk, many=True, missing=list)
    attached_volumes = model.Dependency(storage.Attachment, many=True,
                                        missing=list)
    # TODO: ports

    def equals(self, other):
        # pylint: disable=no-member
        if super(Server, self).equals(other):
            return True
        # TODO: consider comparing metadata
        # TODO: consider comparing security_groups
        if not self.tenant.equals(other.tenant):
            return False
        if not self.flavor.equals(other.flavor):
            return False
        if not self.image.equals(other.image):
            return False
        if self.key_name != other.key_name or self.name != other.name:
            return False
        return True
