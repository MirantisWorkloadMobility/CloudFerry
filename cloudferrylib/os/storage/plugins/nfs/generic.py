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

from cloudferrylib.base import exception
from cloudferrylib.os.storage.plugins import base
from cloudferrylib.os.storage.plugins import copy_mechanisms
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


def generate_volume_pattern(volume_template, volume_id):
    try:
        return volume_template % volume_id
    except TypeError:
        msg = "Invalid volume name template '%s' specified in config."
        LOG.error(msg)
        raise exception.InvalidConfigException(msg)


class NFSPlugin(base.CinderMigrationPlugin):
    """Adds support for NFS cinder backends, such as NetApp NFS, and generic
    cinder NFS driver.

    Looks for cinder volume objects on source controller in
    `nfs_mount_point_base` folder based on `volume_name_template` pattern.

    Required configuration:
     - [[src|dst]_storage] volume_name_template
     - [[src|dst]_storage] nfs_mount_point_base
    """

    PLUGIN_NAME = "nfs"

    @classmethod
    def from_context(cls, _):
        return cls()

    def get_volume_object(self, context, volume_id):
        """:raises: VolumeObjectNotFoundError in case object is not found"""
        controller = context.cloud_config.cloud.ssh_host
        user = context.cloud_config.cloud.ssh_user
        paths = context.cloud_config.storage.nfs_mount_point_bases
        volume_template = context.cloud_config.storage.volume_name_template

        volume_pattern = generate_volume_pattern(volume_template, volume_id)

        rr = remote_runner.RemoteRunner(controller, user, ignore_errors=True)

        for mount_point in paths:
            # errors are ignored to avoid "Filesystem loop detected" messages
            # which don't matter anyways
            find = "find {mount_point} -name '{volume_pattern}' 2>/dev/null"
            res = rr.run(find.format(mount_point=mount_point,
                                     volume_pattern=volume_pattern))

            if res:
                # there should only be one file matching
                path = res.stdout.splitlines().pop()
                return copy_mechanisms.CopyObject(host=controller, path=path)

        msg = ("Volume object for volume '{volume_id}' not found. Either "
               "volume exists in DB, but is not present on storage, or "
               "'nfs_mount_point_bases' is set incorrectly in config")
        raise base.VolumeObjectNotFoundError(msg.format(volume_id=volume_id))
