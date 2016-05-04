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


@model.type_alias('volume_attachments')
class Attachment(model.Model):
    object_id = model.PrimaryKey()
    server = model.Reference('cloudferry.model.compute.Server',
                             ensure_existence=False)
    volume = model.Dependency('cloudferry.model.storage.Volume')
    device = model.String(required=True)

    def equals(self, other):
        # pylint: disable=no-member
        if super(Attachment, self).equals(other):
            return True
        if self.server is None:
            return False
        return self.server.equals(other.server) and self.device == other.device


@model.type_alias('volumes')
class Volume(model.Model):
    object_id = model.PrimaryKey()
    name = model.String(required=True, allow_none=True)
    description = model.String(required=True, allow_none=True)
    availability_zone = model.String(required=True)
    encrypted = model.Boolean(missing=False)
    host = model.String(required=True)
    size = model.Integer(required=True)
    tenant = model.Dependency(identity.Tenant, required=True)
    metadata = model.Dict(missing=dict)
    volume_type = model.String(required=True)
