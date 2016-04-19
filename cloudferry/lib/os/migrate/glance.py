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
import logging
import random
import re

from cloudferry.lib.os import clients
from cloudferry.lib.os import cloud_db
from cloudferry.lib.os import consts
from cloudferry.lib.os.discovery import glance
from cloudferry.lib.os.discovery import model
from cloudferry.lib.os.discovery import nova
from cloudferry.lib.os.migrate import base
from cloudferry.lib.utils import qemu_img
from cloudferry.lib.utils import remote
from cloudferry.lib.utils import taskflow_utils

from glanceclient import exc

LOG = logging.getLogger(__name__)


class BaseImageMigrationTask(base.ObjectTask):
    # pylint: disable=abstract-method

    def __init__(self, image, config, migration):
        super(BaseImageMigrationTask, self).__init__(image)
        self.config = config
        self.migration = migration
        self.created_image = None

    @property
    def src_glance(self):
        src_cloud = self.config.clouds[self.migration.source]
        return clients.image_client(src_cloud)

    @property
    def dst_glance(self):
        dst_cloud = self.config.clouds[self.migration.destination]
        return clients.image_client(dst_cloud)


class ReserveImage(BaseImageMigrationTask):
    default_provides = ['dst_object']

    def migrate(self, *args, **kwargs):
        # TODO: update image properties related to Snapshots
        # TODO: support image created from URL
        source = self.src_object
        dst_cloud = self.config.clouds[self.migration.destination]
        try:
            self.created_image = self.dst_glance.images.create(
                id=source.primary_key.id,
                name=source.name,
                container_format=source.container_format,
                disk_format=source.disk_format,
                is_public=source.is_public,
                protected=source.protected,
                owner=taskflow_utils.map_object_id(source.tenant, dst_cloud),
                size=source.size,
                properties=source.properties)
        except exc.HTTPConflict:
            image = self.dst_glance.images.get(source.primary_key.id)
            if image.status == 'deleted':
                self._reset_dst_image_status()
                self._update_dst_image()
            else:
                self._delete_dst_image()
                self._reset_dst_image_status()
                self._update_dst_image()

        result = glance.Image.load_from_cloud(dst_cloud, self.created_image)
        return [result]

    def revert(self, *args, **kwargs):
        if self.created_image is not None:
            self._delete_dst_image()

    def _delete_dst_image(self):
        dst_glance = self.dst_glance
        image_id = self.src_object.object_id.id
        dst_glance.images.update(image_id, protected=False)
        dst_glance.images.delete(image_id)

    def _update_dst_image(self):
        source = self.src_object
        dst_cloud = self.config.clouds[self.migration.destination]
        self.created_image = self.dst_glance.images.update(
            source.primary_key.id,
            name=source.name,
            container_format=source.container_format,
            disk_format=source.disk_format,
            is_public=source.is_public,
            protected=source.protected,
            owner=taskflow_utils.map_object_id(source.tenant, dst_cloud),
            size=source.size,
            properties=source.properties)

    def _reset_dst_image_status(self):
        dst_cloud = self.config.clouds[self.migration.destination]
        with cloud_db.connection(dst_cloud.glance_db) as db:
            db.execute('UPDATE images SET deleted_at=NULL, deleted=0, '
                       'status=\'queued\' WHERE id=%(image_id)s',
                       image_id=self.src_object.primary_key.id)


class _FileLikeProxy(object):
    # TODO: Merge with cloudferry.lib.utils.file_proxy stuff
    def __init__(self, iterable):
        self.iterable = iterable
        self.buf = bytes()

    def _fill_buf(self, size):
        """
        Fill buffer to contain at least ``size`` bytes.
        """
        while True:
            chunk = next(self.iterable, None)
            if chunk is None:
                break
            self.buf += bytes(chunk)
            if size is not None and len(self.buf) >= size:
                break

    def read(self, size=None):
        if size is None or len(self.buf) < size:
            self._fill_buf(size)
        if size is None:
            result, self.buf = self.buf, ''
        else:
            result, self.buf = self.buf[:size], self.buf[size:]
        return result


class UploadImage(BaseImageMigrationTask):
    def migrate(self, dst_object, *args, **kwargs):
        if self.src_object.status == 'deleted':
            return
        image_id = dst_object.object_id.id
        image_data = _FileLikeProxy(self.src_glance.images.data(image_id))
        self.dst_glance.images.update(image_id, data=image_data)


class UploadDeletedImage(BaseImageMigrationTask):
    def migrate(self, dst_object, *args, **kwargs):
        if self.src_object.status != 'deleted':
            return
        dst_image_id = dst_object.object_id.id
        with model.Session() as session:
            for server in self.get_image_booted_servers(session):
                if self.upload_server_image(server, dst_image_id):
                    break
            else:
                LOG.warning('Unable to restore image %s: no servers found')

    def get_image_booted_servers(self, session):
        servers = []
        for server in session.list(nova.Server, self.migration.source):
            if server.image and server.image == self.src_object:
                servers.append(server)
        random.shuffle(servers)
        return servers

    def upload_server_image(self, server, dst_image_id):
        # pylint: disable=undefined-loop-variable
        for disk in server.ephemeral_disks:
            if disk.path.endswith('disk'):
                break
        else:
            return False

        src_cloud = self.config.clouds[self.migration.source]
        with remote.RemoteExecutor(
                src_cloud, server.hypervisor_hostname) as remote_executor:
            disk_info = qemu_img.get_disk_info(remote_executor, disk.path)
            image_path = disk_info.backing_filename
            if image_path is None:
                return False
            image_info = qemu_img.get_disk_info(remote_executor, image_path)
            image_format = image_info.format
            if image_format is None:
                return False
            try:
                size_str = remote_executor.sudo(
                    'stat -c %s {path}', path=image_path)
            except remote.RemoteFailure:
                return False
            cloud = self.config.clouds[self.migration.destination]
            token = clients.get_token(cloud.credential, cloud.scope)
            endpoint = clients.get_endpoint(cloud.credential, cloud.scope,
                                            consts.ServiceType.IMAGE)
            curl_output = remote_executor.sudo(
                'curl -X PUT -w "\\n\\n<http_status=%{{http_code}}>" '
                '-H "X-Auth-Token: {token}" '
                '-H "Content-Type: application/octet-stream" '
                '-H "x-image-meta-disk_format: {disk_format}" '
                '-H "x-image-meta-size: {image_size}" '
                '--data-binary @"{image_path}" '
                '"{endpoint}/v1/images/{image_id}"',
                token=token, endpoint=endpoint, image_id=dst_image_id,
                image_path=image_path, disk_format=image_format,
                image_size=int(size_str))
            match = re.search(r'<http_status=(\d+)>', curl_output)
            if match is None or int(match.group(1)) != 200:
                LOG.error('Failed to upload image: %s', curl_output)
                return False
            return True


class ImageMigrationFlowFactory(base.MigrationFlowFactory):
    migrated_class = glance.Image

    def create_flow(self, config, migration, obj):
        return [
            ReserveImage(obj, config, migration),
            UploadImage(obj, config, migration),
            UploadDeletedImage(obj, config, migration),
            base.RememberMigration(obj),
        ]
