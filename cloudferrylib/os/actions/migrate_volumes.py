# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Cinder volume copy """

import logging
import multiprocessing
from itertools import izip
from itertools import repeat

from cinderclient import exceptions as cinder_exceptions
from cinderclient.v1 import volumes as volumes_v1
from cinderclient.v2 import volumes as volumes_v2

from cloudferrylib.base import exception
from cloudferrylib.base.action import action
from cloudferrylib.os.actions import cinder_database_manipulation
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.storage import plugins
from cloudferrylib.os.storage.plugins import copy_mechanisms
from cloudferrylib.utils import retrying
from cloudferrylib.utils import utils

LOG = logging.getLogger(__name__)


def _vol_name(vol_id, vol_name):
    return "{name} ({uuid})".format(
        uuid=vol_id,
        name=vol_name or "<no name>")


def vol_name_from_dict(volume_dict):
    return _vol_name(volume_dict['id'], volume_dict['display_name'])


def vol_name_from_obj(volume_object):
    return _vol_name(volume_object.id, volume_object.display_name)


def volume_name(volume):
    if isinstance(volume, dict):
        return vol_name_from_dict(volume)
    elif isinstance(volume, (volumes_v1.Volume, volumes_v2.Volume)):
        return vol_name_from_obj(volume)


class VolumeMigrationView(object):
    def __init__(self, volumes):
        self.volumes = volumes
        self.num_volumes = len(self.volumes)
        self.total_size = sum((v['size'] for v in self.volumes))
        self.size_migrated = 0

    def initial_message(self):
        LOG.info("Starting migration of %s volumes of total %sGB",
                 self.num_volumes, self.total_size)

    def before_migration(self, i, v):
        n = i + 1
        progress = ""

        # avoid division by zero
        if self.num_volumes:
            percentage = float(i) / self.num_volumes
            progress = "{n} of {total}, {percentage:.1%}".format(
                n=n, total=self.num_volumes, percentage=percentage)

        LOG.info("Starting migration of volume '%(name)s' of "
                 "size %(size)dGB, %(progress)s",
                 {'name': volume_name(v),
                  'size': v['size'],
                  'progress': progress})

    def after_migration(self, i, v):
        n = i + 1
        progress = ""
        size_progress = ""

        # avoid division by zero
        if self.num_volumes:
            percentage = float(n) / self.num_volumes
            progress = "{n} of {total}, {percentage:.1%}".format(
                n=n, total=self.num_volumes, percentage=percentage)

        if self.total_size:
            self.size_migrated += v['size']
            size_percentage = float(self.size_migrated) / self.total_size
            size_progress = "{n}GB of {total}GB, {percentage:.1%}".format(
                n=self.size_migrated,
                total=self.total_size,
                percentage=size_percentage)

        LOG.info("Finished migration of volume '%s'", volume_name(v))
        LOG.info("Volume migration status: %(progress)s",
                 {'progress': '; '.join([progress, size_progress])})


class MigrateVolumes(action.Action):
    """Copies cinder volumes from source to destination cloud sequentially

    All migrated volumes have 'src_volume_id' metadata field which allows
    identifying volumes migrated previously.

    Depends on:
     - `get_volumes_db_data` task (`GetVolumesDb` class)
    """

    def __init__(self, init):
        super(MigrateVolumes, self).__init__(init)
        self.src_cinder_backend = plugins.get_cinder_backend(self.src_cloud)
        self.dst_cinder_backend = plugins.get_cinder_backend(self.dst_cloud)

    def get_cinder_volumes(self, **kwargs):
        cinder_volumes_data = kwargs.get('cinder_database')

        if cinder_volumes_data is None:
            vol_get = cinder_database_manipulation.GetVolumesDb(self.src_cloud)
            cinder_volumes_data = vol_get.run(**kwargs)

        return cinder_volumes_data['volumes']

    def migrate_volume(self, src_volume):
        """Creates volume on destination and copies volume data from source"""
        LOG.info("Checking if volume '%s' already present in destination",
                 volume_name(src_volume))
        dst_cinder = self.dst_cloud.resources[utils.STORAGE_RESOURCE]

        dst_volume = dst_cinder.get_migrated_volume(src_volume['id'])
        volume_exists_in_destination = (dst_volume is not None and
                                        dst_volume.status in ['available',
                                                              'in-use'])

        if not volume_exists_in_destination:
            try:
                src_volume_object = self.src_cinder_backend.get_volume_object(
                    self.src_cloud, src_volume['id'])
                LOG.debug("Backing file for source volume: %s",
                          src_volume_object)

                dst_volume = self._create_volume(src_volume)

                # It takes time to create volume object
                timeout = self.cfg.migrate.storage_backend_timeout
                retryer = retrying.Retry(max_time=timeout)
                dst_volume_object = retryer.run(
                    self.dst_cinder_backend.get_volume_object,
                    self.dst_cloud, dst_volume.id)

                LOG.debug("Backing file for volume in destination: %s",
                          dst_volume_object)
                LOG.info("Starting volume copy from %s to %s",
                         src_volume_object, dst_volume_object)
                self.copy_volume_data(src_volume_object, dst_volume_object)
            except (plugins.base.VolumeObjectNotFoundError,
                    retrying.TimeoutExceeded,
                    exception.TenantNotPresentInDestination,
                    cinder_exceptions.OverLimit,
                    copy_mechanisms.CopyFailed) as e:
                LOG.warning("%(error)s, volume %(name)s will be skipped",
                            {'error': e.message,
                             'name': volume_name(src_volume)})

                if dst_volume is not None:
                    msg = ("Removing volume {name} from destination "
                           "since it didn't migrate properly".format(
                            name=volume_name(dst_volume)))
                    LOG.info(msg)
                    self.delete_volume(dst_volume)
            finally:
                if dst_volume is not None:
                    self.dst_cinder_backend.cleanup(self.cloud,
                                                    dst_volume.id)
        else:
            LOG.info("Volume '%s' is already present in destination cloud, "
                     "skipping", src_volume['id'])

        return dst_volume

    def _create_volume(self, src_volume):
        src_keystone = self.src_cloud.resources[utils.IDENTITY_RESOURCE]
        dst_keystone = self.dst_cloud.resources[utils.IDENTITY_RESOURCE]
        dst_cinder = self.dst_cloud.resources[utils.STORAGE_RESOURCE]

        dst_tenant = keystone.get_dst_tenant_from_src_tenant_id(
            src_keystone, dst_keystone, src_volume['project_id'])
        if dst_tenant is None:
            msg = ("Tenant '{}' does not exist in destination, make sure "
                   "you migrated tenants.").format(
                src_volume['project_id'])
            LOG.warning(msg)
            raise exception.TenantNotPresentInDestination(msg)

        LOG.info("Creating volume of size %sG in tenant %s in destination",
                 src_volume['size'], dst_tenant.name)
        dst_volume = dst_cinder.create_volume_from_volume(src_volume,
                                                          dst_tenant.id)
        LOG.info("Volume created: %s", volume_name(dst_volume))

        return dst_volume

    def run(self, **kwargs):
        """:returns: dictionary {<source-volume-id>: <destination-volume>}"""
        new_volumes = {}
        volumes = self.get_cinder_volumes(**kwargs)
        volumes = [v['volume'] for v in volumes.itervalues()]

        view = VolumeMigrationView(volumes)
        view.initial_message()

        for i, volume in enumerate(volumes):
            view.before_migration(i, volume)

            migrated_volume = self.migrate_volume(volume)

            view.after_migration(i, volume)
            new_volumes[volume['id']] = migrated_volume
        return new_volumes

    def copy_volume_data(self, src_volume_object, dst_volume_object):
        copier = plugins.copy_mechanism_from_plugin_names(
            self.src_cinder_backend.PLUGIN_NAME,
            self.dst_cinder_backend.PLUGIN_NAME)
        if src_volume_object is not None and dst_volume_object is not None:
            copier.copy(self, src_volume_object, dst_volume_object)

    def delete_volume(self, volume_id):
        dst_storage = self.dst_cloud.resources[utils.STORAGE_RESOURCE]
        cinder_client = dst_storage.get_client()
        cinder_client.volumes.delete(volume_id)


class MigrateVolumesParallel(action.Action):
    """Copies cinder volumes from source to destination cloud in parallel

    Depends on:
     - `get_volumes_db_data` task (`GetVolumesDb` class)

    Config options:
     - [MIGRATE] num_processes_for_volume_migration
    """

    def __init__(self, init):
        super(MigrateVolumesParallel, self).__init__(init)
        self.init = init

    def run(self, **kwargs):
        num_processes = self.cfg.migrate.num_processes_for_volume_migration

        p = multiprocessing.Pool(processes=num_processes)

        migrate_action = MigrateVolumes(self.init)
        volumes = migrate_action.get_cinder_volumes(**kwargs)
        try:
            p.map_async(migrate_action.migrate_volume,
                        izip(repeat(migrate_action), volumes))
        finally:
            p.close()
            p.join()
