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

from marshmallow import fields
from cinderclient import exceptions as cinder_exceptions

from cloudferrylib.os.discovery import keystone
from cloudferrylib.os.discovery import model

LOG = logging.getLogger(__name__)


class Attachment(model.Model):
    class Schema(model.Schema):
        server_id = fields.String(required=True)  # TODO: model.Reference
        device = fields.String(required=True)


@model.type_alias('volumes')
class Volume(model.Model):
    class Schema(model.Schema):
        object_id = model.PrimaryKey('id')
        name = fields.String(required=True, allow_none=True)
        description = fields.String(required=True, allow_none=True)
        availability_zone = fields.String(required=True)
        encrypted = fields.Boolean(missing=False)
        host = fields.String(required=True)
        snapshot_id = fields.String(required=True, allow_none=True)
        source_volid = fields.String(required=True, allow_none=True)
        size = fields.Integer(required=True)
        tenant = model.Dependency(keystone.Tenant, required=True)
        metadata = fields.Dict(missing=dict)
        volume_type = fields.String(required=True)
        attachments = model.Nested(Attachment, many=True, missing=list)

        FIELD_MAPPING = {
            'name': 'display_name',
            'description': 'display_description',
            'host': 'os-vol-host-attr:host',
            'tenant': 'os-vol-tenant-attr:tenant_id',
        }

    @classmethod
    def load_missing(cls, cloud, object_id):
        volume_client = cloud.volume_client()
        try:
            raw_volume = volume_client.volumes.get(object_id.id)
            return Volume.load_from_cloud(cloud, raw_volume)
        except cinder_exceptions.NotFound:
            return None

    @classmethod
    def discover(cls, cloud):
        volume_client = cloud.volume_client()
        volumes_list = volume_client.volumes.list(
            search_opts={'all_tenants': True})
        with model.Session() as session:
            for raw_volume in volumes_list:
                volume = Volume.load_from_cloud(cloud, raw_volume)
                session.store(volume)
