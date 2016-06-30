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

from cinderclient import exceptions as cinder_exceptions
from novaclient import exceptions as nova_exceptions

from cloudferry import discover
from cloudferry import model
from cloudferry.model import compute
from cloudferry.model import identity
from cloudferry.model import storage
from cloudferry.lib.os import clients

LOG = logging.getLogger(__name__)


class VolumeDiscoverer(discover.Discoverer):
    discovered_class = storage.Volume

    def discover_all(self):
        volumes = []
        volume_client = clients.volume_client(self.cloud)
        for raw_volume in self.retry(volume_client.volumes.list,
                                     search_opts={'all_tenants': True},
                                     returns_iterable=True):
            try:
                volumes.append(self.load_from_cloud(raw_volume))
            except model.ValidationError as e:
                LOG.warning('Invalid volume %s in cloud %s: %s',
                            raw_volume.id, self.cloud.name, e)
        with model.Session() as session:
            for volume in volumes:
                session.store(volume)

    def discover_one(self, uuid):
        volume_client = clients.volume_client(self.cloud)
        try:
            volume = self.load_from_cloud(
                self.retry(volume_client.volumes.get, uuid,
                           expected_exceptions=[cinder_exceptions.NotFound]))
            with model.Session() as session:
                session.store(volume)
                return volume
        except cinder_exceptions.NotFound:
            raise discover.NotFound()

    def load_from_cloud(self, data):
        volume_dict = {
            'object_id': self.make_id(data.id),
            'name': data.display_name,
            'description': data.display_description,
            'host': getattr(data, 'os-vol-host-attr:host'),
            'tenant': self.find_ref(
                identity.Tenant,
                getattr(data, 'os-vol-tenant-attr:tenant_id')),
        }
        for attr_name in ('availability_zone', 'size', 'volume_type',
                          'encrypted', 'metadata'):
            if hasattr(data, attr_name):
                volume_dict[attr_name] = getattr(data, attr_name)
        return storage.Volume.load(volume_dict)


class AttachmentDiscoverer(discover.Discoverer):
    discovered_class = storage.Attachment

    def discover_all(self):
        volume_client = clients.volume_client(self.cloud)
        raw_volumes = self.retry(volume_client.volumes.list,
                                 search_opts={'all_tenants': True},
                                 returns_iterable=True)
        attachments = []
        for raw_volume in raw_volumes:
            for raw_attachment in raw_volume.attachments:
                try:
                    attachment = self.load_from_cloud(raw_attachment)
                    attachments.append(attachment)
                except model.ValidationError as e:
                    LOG.warning('Invalid attachment %s in cloud %s: %s',
                                raw_attachment['id'], self.cloud.name, e)
        with model.Session() as session:
            for attachment in attachments:
                session.store(attachment)

    def discover_one(self, uuid):
        server_id, volume_id = uuid.split(':')
        compute_client = clients.compute_client(self.cloud)
        try:
            raw_attachment = self.retry(
                compute_client.volumes.get_server_volume, server_id, volume_id,
                expected_exceptions=[nova_exceptions.NotFound])
            attachment = self.load_from_cloud(raw_attachment)
            with model.Session() as session:
                session.store(attachment)
                return attachment
        except nova_exceptions.NotFound:
            raise discover.NotFound()

    def load_from_cloud(self, data):
        if isinstance(data, dict):
            server_id = data['server_id']
            volume_id = data['volume_id']
            device = data['device']
        else:
            server_id = data.serverId
            volume_id = data.volumeId
            device = data.device
        return storage.Attachment.load({
            'object_id': self.make_id('{0}:{1}'.format(server_id, volume_id)),
            'server': {
                'id': server_id,
                'cloud': self.cloud.name,
                'type': compute.Server.get_class_qualname(),
            },
            'volume': self.find_ref(storage.Volume, volume_id),
            'device': device,
        })
