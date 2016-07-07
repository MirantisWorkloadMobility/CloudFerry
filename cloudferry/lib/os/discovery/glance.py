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

from cloudferry import discover
from cloudferry import model
from cloudferry.model import identity
from cloudferry.model import image
from cloudferry.lib.os import clients

LOG = logging.getLogger(__name__)


class ImageMemberDiscoverer(discover.Discoverer):
    discovered_class = image.ImageMember

    def discover_all(self):
        # No point doing this
        return

    def discover_one(self, uuid):
        image_id, member_id = uuid.split(':')
        image_member = self.load_from_cloud(
            dict(uuid=uuid, image_id=image_id, member_id=member_id))
        with model.Session() as session:
            session.store(image_member)
            return image_member

    def load_from_cloud(self, data):
        uuid = data.get('uuid')
        image_id = data['image_id']
        member_id = data['member_id']
        if uuid is None:
            uuid = '{0}:{1}'.format(image_id, member_id)
        return image.ImageMember.load({
            'object_id': self.make_id(uuid),
            'image': self.find_ref(image.Image, image_id),
            'member': self.find_ref(identity.Tenant, member_id),
        })


class ImageDiscoverer(discover.Discoverer):
    discovered_class = image.Image

    def discover_all(self):
        images = []
        image_client = clients.image_client(self.cloud)
        raw_images = self.retry(image_client.images.list,
                                filters={'is_public': None,
                                         'status': 'active'},
                                returns_iterable=True)
        for raw_image in raw_images:
            try:
                images.append(self.load_from_cloud(raw_image))
            except model.ValidationError as e:
                LOG.warning('Invalid image %s in cloud %s: %s',
                            raw_image.id, self.cloud.name, e)

        with model.Session() as session:
            for img in images:
                session.store(img)

        for img in images:
            self._populate_members(img, image_client)

    def discover_one(self, uuid):
        image_client = clients.image_client(self.cloud)
        try:
            raw_image = self.retry(
                image_client.images.get, uuid,
                expected_exceptions=[glance_exc.HTTPNotFound])
            img = self.load_from_cloud(raw_image)
            with model.Session() as session:
                session.store(img)
            self._populate_members(img, image_client)
            return img
        except glance_exc.HTTPNotFound:
            raise discover.NotFound()

    def load_from_cloud(self, data):
        image_dict = {
            'object_id': self.make_id(data.id),
            'tenant': self.find_ref(identity.Tenant, data.owner),
        }
        for attr_name in ('name', 'status', 'checksum', 'size', 'virtual_size',
                          'is_public', 'protected', 'container_format',
                          'disk_format', 'min_disk', 'min_ram', 'properties'):
            if hasattr(data, attr_name):
                image_dict[attr_name] = getattr(data, attr_name)
        return image.Image.load(image_dict)

    def _populate_members(self, img, image_client):
        try:
            raw_members = self.retry(
                image_client.image_members.list, image=img.object_id.id,
                expected_exceptions=[glance_exc.HTTPNotFound],
                returns_iterable=True)
            for raw_member in raw_members:
                member = self.find_ref(image.ImageMember,
                                       '{0}:{1}'.format(raw_member.image_id,
                                                        raw_member.member_id))
                img.members.append(member)
        except glance_exc.HTTPNotFound:
            return
