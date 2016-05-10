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
from cloudferry.lib.utils import remote

from glanceclient import exc as glance_exc

LOG = logging.getLogger(__name__)


class BaseImageMigrationTask(base.MigrationTask):
    # pylint: disable=abstract-method

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
            self.created_object = self.dst_glance.images.create(
                id=source.primary_key.id,
                name=source.name,
                container_format=source.container_format,
                disk_format=source.disk_format,
                is_public=source.is_public,
                protected=source.protected,
                owner=source.tenant.get_uuid_in(dst_cloud.name),
                size=source.size,
                properties=source.properties)
        except glance_exc.HTTPConflict:
            image = self.dst_glance.images.get(source.primary_key.id)
            if image.status == 'deleted':
                _reset_dst_image_status(self)
                self._update_dst_image()
            else:
                self._delete_dst_image()
                _reset_dst_image_status(self)
                self._update_dst_image()

        result = glance.Image.load_from_cloud(dst_cloud, self.created_object)
        return dict(dst_object=result)

    def revert(self, *args, **kwargs):
        if self.created_object is not None:
            self._delete_dst_image()

    def _delete_dst_image(self):
        dst_glance = self.dst_glance
        image_id = self.src_object.object_id.id
        dst_glance.images.update(image_id, protected=False)
        dst_glance.images.delete(image_id)

    def _update_dst_image(self):
        source = self.src_object
        dst_cloud = self.config.clouds[self.migration.destination]
        self.created_object = self.dst_glance.images.update(
            source.primary_key.id,
            name=source.name,
            container_format=source.container_format,
            disk_format=source.disk_format,
            is_public=source.is_public,
            protected=source.protected,
            owner=source.tenant.get_uuid_in(dst_cloud.name),
            size=source.size,
            properties=source.properties)


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
    default_provides = ['need_restore_deleted']

    def migrate(self, dst_object, *args, **kwargs):
        if self.src_object.status == 'deleted':
            return dict(need_restore_deleted=True)
        image_id = dst_object.object_id.id
        try:
            image_data = _FileLikeProxy(self.src_glance.images.data(image_id))
            self.dst_glance.images.update(image_id, data=image_data)
            return dict(need_restore_deleted=False)
        except glance_exc.HTTPNotFound:
            return dict(need_restore_deleted=True)


class UploadDeletedImage(BaseImageMigrationTask):
    def migrate(self, dst_object, need_restore_deleted, *args, **kwargs):
        if not need_restore_deleted:
            return
        dst_image_id = dst_object.object_id.id
        with model.Session() as session:
            boot_disk_infos = self._get_boot_disk_locations(session)

        for boot_disk_info in boot_disk_infos:
            if self.upload_server_image(boot_disk_info, dst_image_id):
                return
        raise base.AbortMigration(
            'Unable to restore deleted image %s: no servers found',
            dst_image_id)

    def _get_boot_disk_locations(self, session):
        boot_disk_infos = []
        for server in session.list(nova.Server, self.migration.source):
            if not server.image or server.image != self.src_object:
                continue
            for disk in server.ephemeral_disks:
                if disk.base_path is not None and disk.path.endswith('disk'):
                    assert disk.base_size is not None
                    assert disk.base_format is not None
                    boot_disk_infos.append({
                        'host': server.hypervisor_hostname,
                        'base_path': disk.base_path,
                        'base_size': disk.base_size,
                        'base_format': disk.base_format,
                    })
                    break

        random.shuffle(boot_disk_infos)
        return boot_disk_infos

    def upload_server_image(self, boot_disk_info, dst_image_id):
        src_cloud = self.config.clouds[self.migration.source]
        host = boot_disk_info['host']
        image_path = boot_disk_info['base_path']
        image_format = boot_disk_info['base_format']
        image_size = boot_disk_info['base_size']
        cloud = self.config.clouds[self.migration.destination]
        token = clients.get_token(cloud.credential, cloud.scope)
        endpoint = clients.get_endpoint(cloud.credential, cloud.scope,
                                        consts.ServiceType.IMAGE)
        _reset_dst_image_status(self)
        with remote.RemoteExecutor(src_cloud, host) as remote_executor:
            curl_output = remote_executor.sudo(
                'curl -X PUT -w "\\n\\n<http_status=%{{http_code}}>" '
                '-H "X-Auth-Token: {token}" '
                '-H "Content-Type: application/octet-stream" '
                '-H "x-image-meta-disk_format: {disk_format}" '
                '-H "x-image-meta-size: {image_size}" '
                '--upload-file "{image_path}" '
                '"{endpoint}/v1/images/{image_id}"',
                token=token, endpoint=endpoint, image_id=dst_image_id,
                image_path=image_path, disk_format=image_format,
                image_size=image_size)
            match = re.search(r'<http_status=(\d+)>', curl_output)
            if match is None or int(match.group(1)) != 200:
                LOG.error('Failed to upload image: %s', curl_output)
                return False
            return True


def _reset_dst_image_status(task):
    dst_cloud = task.config.clouds[task.migration.destination]
    with cloud_db.connection(dst_cloud.glance_db) as db:
        db.execute('UPDATE images SET deleted_at=NULL, deleted=0, '
                   'status=\'queued\', checksum=NULL WHERE id=%(image_id)s',
                   image_id=task.src_object.primary_key.id)


class ImageMigrationFlowFactory(base.MigrationFlowFactory):
    migrated_class = glance.Image

    def create_flow(self, config, migration, obj):
        return [
            ReserveImage(obj, config, migration),
            UploadImage(obj, config, migration),
            UploadDeletedImage(obj, config, migration),
            base.RememberMigration(obj, config, migration),
        ]


class MigrateImageMember(BaseImageMigrationTask):
    default_provides = ['dst_object']

    def migrate(self, *args, **kwargs):
        src_object = self.src_object
        dst_cloud = self.config.clouds[self.migration.destination]
        dst_image_id = src_object.image.get_uuid_in(dst_cloud.name)
        dst_tenant_id = src_object.member.get_uuid_in(dst_cloud.name)
        self.dst_glance.image_members.create(dst_image_id, dst_tenant_id,
                                             src_object.can_share)

        image_member = glance.ImageMember.make(
            dst_cloud, dst_image_id, dst_tenant_id, src_object.can_share)
        return dict(dst_object=image_member)

    def revert(self, *args, **kwargs):
        src_object = self.src_object
        dst_cloud = self.config.clouds[self.migration.destination]
        dst_image_id = src_object.image.get_uuid_in(dst_cloud.name)
        dst_tenant_id = src_object.member.get_uuid_in(dst_cloud.name)
        self.dst_glance.image_members.delete(dst_image_id, dst_tenant_id)


class ImageMemberMigrationFlowFactory(base.MigrationFlowFactory):
    migrated_class = glance.ImageMember

    def create_flow(self, config, migration, obj):
        return [
            MigrateImageMember(obj, config, migration),
            base.RememberMigration(obj, config, migration),
        ]
