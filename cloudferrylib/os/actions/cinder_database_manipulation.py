"""Cinder Database Manipulation."""
# Copyright (c) 2014 Mirantis Inc.
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


import abc
import copy
import os
import time

from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.copy_engines import base
from cloudferrylib.utils import files
from cloudferrylib.utils import local
from cloudferrylib.utils import log
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import sizeof_format
from cloudferrylib.utils import utils
from cloudferrylib.views import cinder_storage_view

LOG = log.getLogger(__name__)

NAMESPACE_CINDER_CONST = "cinder_database"

AVAILABLE = 'available'
CINDER_VOLUME = "cinder-volume"
HOST = 'host'
SSH_HOST = 'ssh_host'
BY_VTID = 'by_vtid'
ALL = 'all'
MOUNT_DELIM = '='
DEFAULT = 'default'
SRC = 'src'
DST = 'dst'
CLOUD = 'cloud'
RES = 'res'
CFG = 'cfg'
METADATA_TABLES = ('volume_metadata', 'volume_glance_metadata')

AWK_GET_MOUNTED_PREFIX = (
    "/^nfs_shares_config/ "
    "{res=$2} "
)
AWK_GET_MOUNTED_IN_BLOCK = (
    " i && res && "
    r"/^\[.*\]/{exit} "
)
AWK_GET_MOUNTED_SUFFIX = (
    " END{print res}'"
    " '%s' | xargs grep -v '^#'); "
    "do mount | "
    "awk '{if (match($1, \"^'$exp'$\") && $3 ~ \"cinder\") "
)
AWK_GET_MOUNTED_NFS_SHARES = ''.join([
    AWK_GET_MOUNTED_PREFIX,
    AWK_GET_MOUNTED_IN_BLOCK,
    AWK_GET_MOUNTED_SUFFIX
])
AWK_GET_MOUNTED_LAST_NFS_SHARES = ''.join([
    AWK_GET_MOUNTED_PREFIX,
    AWK_GET_MOUNTED_SUFFIX
])

QUOTA_RESOURCES = ('volumes', 'gigabytes')


def _remote_runner(cloud):
    return remote_runner.RemoteRunner(cloud[CFG].get(HOST),
                                      cloud[CFG].ssh_user,
                                      cloud[CFG].ssh_sudo_password,
                                      sudo=True,
                                      gateway=cloud[CFG].get(SSH_HOST))


def _volume_types_map(data):
    return dict([(t['name'], t['id']) for t in data.get('volume_types', [])])


def _volume_types(data):
    return data.get('volume_types', [])


def _modify_data(data):
    for volume in data['volumes']:
        if volume.get('status', '') != AVAILABLE:
            volume['mountpoint'] = None
            volume['status'] = 'available'
            volume['instance_uuid'] = None
            volume['attach_status'] = 'detached'
    return data


def _clean_data(data):
    # disregard volume types
    if 'volume_types' in data:
        del data['volume_types']
    if 'volume_type_extra_specs' in data:
        del data['volume_type_extra_specs']
    return data


class CinderDatabaseInteraction(action.Action):

    """Abstract Action class."""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def run(self, *args, **kwargs):
        """Run action."""
        pass

    def get_resource(self):
        """
        Get cinder-volume resource.

        :return: cinder_database resource

        """
        cinder_resource = self.cloud.resources.get(
            utils.STORAGE_RESOURCE)
        if not cinder_resource:
            raise exception.AbortMigrationError(
                "No resource {res} found".format(res=utils.STORAGE_RESOURCE))
        return cinder_resource


class GetVolumesDb(CinderDatabaseInteraction):

    """Retrieve Db info."""

    def run(self, *args, **kwargs):
        """
        Run GetVolumesDb action.

        :return: namespace with db info

        """
        return {NAMESPACE_CINDER_CONST:
                self.get_resource().read_info()}


class TransportVolumes(CinderDatabaseInteraction):

    """
    Migrate volumes.

    Depends on 'GetVolumesDb' action, it must be run first.

    """

    def __init__(self, *args, **kwargs):
        super(TransportVolumes, self).__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        """Run TransportVolumes Action."""
        data_from_namespace = kwargs.get(NAMESPACE_CINDER_CONST)
        if not data_from_namespace:
            raise exception.AbortMigrationError(
                "Cannot read attribute {attribute} from namespace".format(
                    attribute=NAMESPACE_CINDER_CONST))

        data = data_from_namespace
        self.get_resource().deploy(data)


class CopyVolumes(object):

    """
    Copy volumes from NFS backend(s) to NFS backend(s).

    Work via rsync, can handle big files
    and resume after errors.

    """

    def __init__(self, cfg, src_cloud, dst_cloud):
        self.ssh_attempts = cfg.migrate.ssh_connection_attempts
        self.key_filename = cfg.migrate.key_filename

        self.storage = {
            SRC: cfg.src_storage,
            DST: cfg.dst_storage,
        }
        self.clouds = {
            SRC: {
                CLOUD: src_cloud,
                RES: src_cloud.resources.get(utils.STORAGE_RESOURCE),
                CFG: cfg.src,
            },
            DST: {
                CLOUD: dst_cloud,
                RES: dst_cloud.resources.get(utils.STORAGE_RESOURCE),
                CFG: cfg.dst,
            }
        }
        self.migration = src_cloud.migration

        self.data = {SRC: {}, DST: {}}

        self.dst_hosts = None
        self.dst_mount = None
        self.dst_dir_to_provider = None
        self.dst_provider_to_vtid = None
        self.dst_volume_types = None
        self.path_map = None
        self.mount_all = {}

    def run(self):
        """Copy volumes and return result data.

        :return: dict

        """
        LOG.info('Start volumes migration process.')
        for position in self.clouds:
            self.data[position] = self.clouds[position][RES].read_info()

        self._skip_existing_volumes()

        self._try_copy_volumes()

        self.data[SRC] = _modify_data(self.data[SRC])
        self.data[SRC] = self.fix_metadata(self.data[SRC])

        self.data[SRC] = _clean_data(self.data[SRC])
        LOG.info('Volumes migration is completed.')
        return self.data[SRC]

    def _skip_existing_volumes(self):
        LOG.info('Start compare existing volumes on the destination cloud. '
                 'If volumes exist on the destination cloud, '
                 'then skip migration for those volumes.')
        res = []
        dst_ids = [v['id'] for v in self.data[DST]['volumes']]
        for v in self.data[SRC]['volumes']:
            if v['id'] in dst_ids:
                LOG.warning('Volume %s(%s) exists, skipping migration.',
                            v.get('display_name', ''), v['id'])
            else:
                res.append(v)
                LOG.info('Volume %s(%s) does not exist on '
                         'the destination cloud, will be migrated.',
                         v.get('display_name', ''),
                         v['id'])
        self.data[SRC]['volumes'] = res

        LOG.info('All volumes on the source and '
                 'destination cloud have been compared.')

    def fix_metadata(self, data):
        """Fix metadata table.

        Replace src image ids by correspoing dst image ids.

        :return: dict

        """
        data = copy.deepcopy(data)
        vol_ids = [v['id'] for v in data['volumes']]
        migrated = self.migration[utils.IMAGE_RESOURCE]

        for table in METADATA_TABLES:
            metadata = data.get(table, {})
            metadata = [m for m in metadata if m['volume_id'] in vol_ids]

            for m in metadata:
                if m['key'] == 'image_id':
                    m['value'] = migrated.migrated_id(m['value'])
            data[table] = metadata
        return data

    def _run_cmd(self, cloud, cmd):
        runner = _remote_runner(cloud)
        output = runner.run(cmd)
        res = output.split('\r\n')
        return res if len(res) > 1 else res[0]

    def run_repeat_on_errors(self, cloud, cmd):
        """Run remote command cmd.

        :return: err or None

        """
        runner = _remote_runner(cloud)
        try:
            runner.run_repeat_on_errors(cmd)
        except remote_runner.RemoteExecutionError as e:
            return e.message

    def find_dir(self, position, paths, v):
        """
        Find file v in paths.

        :return: path to the file

        """
        volume_filename = self.storage[position].volume_name_template + v['id']
        LOG.debug('Looking for %s in %s', volume_filename, repr(paths))
        if not paths:
            return None
        for p in paths:
            cmd = 'ls -1 %s' % p
            lst = self._run_cmd(self.clouds[position], cmd)
            if lst and not isinstance(lst, list):
                lst = [lst]
            if volume_filename in lst:
                LOG.debug('Found %s in %s', volume_filename, p)
                return '%s/%s' % (p, volume_filename)

    def run_transfer(self, src, dst):
        """Run repeating remote commmand.

        :return: True on success (or False otherwise)

        """
        data = {'host_src': self.clouds[SRC][CFG].get(HOST),
                'path_src': src,
                'host_dst': self.clouds[DST][CFG].get(HOST),
                'path_dst': os.path.join(dst, os.path.basename(src)),
                'gateway': self.clouds[SRC][CFG].get(SSH_HOST)}

        copier = base.get_copier(self.clouds[SRC][CLOUD],
                                 self.clouds[DST][CLOUD],
                                 data)
        try:
            copier.transfer(data)
            return True
        except (remote_runner.RemoteExecutionError,
                local.LocalExecutionFailed)as e:
            LOG.debug(e, exc_info=True)
            LOG.warning("Failed copying to %s from %s", dst, src)
            return False

    def volume_size(self, cloud, path):
        """
        Get size of vol_file in bytes.

        :return: int
        """
        runner = _remote_runner(cloud)
        return files.remote_file_size(runner, path)

    def free_space(self, cloud, path):
        """
        Get free space available on `path` in bytes.

        :return: int

        """
        cmd = (
            'df -k "'
            "%s"
            '" | '
            "awk 'FNR == 2 {print $4}'"
        ) % path
        size = self._run_cmd(cloud, cmd)
        # KB -> B
        return int(size) * 1024

    def _clean(self, cloud, filepath):
        cmd = (
            'rm -f %s'
        ) % filepath
        LOG.info("Delete volume %s", filepath)
        self.run_repeat_on_errors(cloud, cmd)

    def transfer_if_enough_space(self, size, src, dst):
        """Copy if enough space.

        :return: True on success (or False otherwise)

        """
        LOG.info('Calculate free space on the destination cloud.')
        dst_free_space = self.free_space(self.clouds[DST], dst)
        if dst_free_space > size:
            LOG.info("Enough space found on %s", dst)
            LOG.info('Start copying volume.')

            return self.run_transfer(src, dst)
        LOG.warning("No enough space on %s", dst)

    def checksum(self, cloud, path):
        """
        Get checksum of `filepath`.

        :return: str
        """

        runner = _remote_runner(cloud)
        return files.remote_md5_sum(runner, path)

    def _transfer(self, src, dstpaths, volume, src_size):
        LOG.debug("Trying transfer file for volume: %s[%s]",
                  volume.get('display_name', None), volume['id'])
        dstfile = self.find_dir(DST, dstpaths, volume)
        LOG.debug("Source file size = %d", src_size)
        LOG.debug("Searching for space for volume: %s[%s]",
                  volume.get('display_name', None), volume['id'])
        if dstfile:
            LOG.info("File found on destination: %s", dstfile)
            dst_size = self.volume_size(self.clouds[DST], dstfile)
            LOG.debug("Destination file (%s) size = %d", dstfile, dst_size)
            dst = os.path.dirname(dstfile)

            LOG.info('Calculate and compare checksums volume on the source '
                     'and on the destionation cloud.')
            if src_size == dst_size:
                src_md5 = self.checksum(self.clouds[SRC], src)
                dst_md5 = self.checksum(self.clouds[DST], dstfile)
                if src_md5 == dst_md5:
                    LOG.info("Destination file %s is up-to-date. "
                             "Sizes and checksums are matched.", dstfile)
                    return dst, 0

            LOG.info('Checksums are different. Start copying volume %s(%s)',
                     volume.get('display_name', ''),
                     volume['id'])
            start_time = time.time()
            if self.transfer_if_enough_space(src_size - dst_size, src, dst):
                elapsed_time = time.time() - start_time
                return dst, elapsed_time
            else:
                LOG.info('Copying volume %s(%s) failed. '
                         'Volume will be deleted.',
                         volume.get('display_name', ''),
                         volume['id'])
                self._clean(self.clouds[DST], dstfile)

        for dst in dstpaths:
            start_time = time.time()
            res = self.transfer_if_enough_space(src_size, src, dst)
            elapsed_time = time.time() - start_time
            if res:
                return dst, elapsed_time
        raise exception.AbortMigrationError('No space found for %s on %s' % (
            str(volume), str(dstpaths)))

    def _mount_output_all(self, position, dirs_only=False):
        if position in self.mount_all \
                and dirs_only in self.mount_all[position]:
            return self.mount_all[position][dirs_only]

        self.mount_all[position] = {}
        self.mount_all[position][dirs_only] = {}

        cmd = (
            "awk -F'[ =\t]+' '/^enabled_backends/{res=$2} END{print res}' \""
            "%s"
            "\" | tr ',' '\n'"
        ) % (self.storage[position].conf)
        backend_blocks = self._run_cmd(self.clouds[position], cmd)
        if backend_blocks and not isinstance(backend_blocks, list):
            backend_blocks = [backend_blocks]
        for backend_block in backend_blocks:
            cmd = (
                r"awk -F'[ =\t]+' '/^\["
                "%s"
                r"\]/{i=1}"
                " i && /^volume_backend_name/ {res=$2}"
                " res && i &&"
                r" /^\[.*\]/{exit}"
                " END{print res}"
                "'"
                " '%s'"
            ) % (backend_block, self.storage[position].conf)
            backend = self._run_cmd(self.clouds[position], cmd)

            vtid = None
            if backend:
                vtids = [sp['volume_type_id']
                         for sp in
                         self.data[position]['volume_type_extra_specs']
                         if sp['key'] == 'volume_backend_name' and
                         sp['value'] == backend]
                vtid = vtids[0] if vtids else None
            print_cmd = ("{print $3}}'; done" if dirs_only
                         else "{print $3\"%s\"$1}}'; done" % MOUNT_DELIM)
            cmd = (
                "for exp in "
                r"$(awk -F'[ =\t]+' '/^\["
                "%s"
                r"\]/{i=1} i && "
            ) % (backend_block)
            cmd += AWK_GET_MOUNTED_NFS_SHARES % self.storage[position].conf
            cmd += print_cmd
            nfs_shares = self._run_cmd(self.clouds[position], cmd)
            if not isinstance(nfs_shares, list):
                nfs_shares = [nfs_shares]
            fld = vtid if vtid else DEFAULT
            if fld not in self.mount_all[position][dirs_only]:
                self.mount_all[position][dirs_only][fld] = set([])
            self.mount_all[position][dirs_only][fld].update(nfs_shares)
        return self.mount_all[position][dirs_only]

    def _mount_output(self, position, vt=None, dirs_only=False):
        if dirs_only:
            print_cmd = "{print $3}}'; done"
        else:
            print_cmd = "{print $3\"%s\"$1}}'; done" % MOUNT_DELIM

        res = None
        if vt:
            res = self._mount_output_all(
                position, dirs_only=dirs_only).get(vt['id'], None)
        if not res:
            res = self._mount_output_all(
                position, dirs_only=dirs_only).get(DEFAULT, None)
        if not res:
            # default nfs_shares_config
            cmd = (
                "for exp in "
                "$(awk -F'[ =\t]+' '"
            )
            cmd += \
                AWK_GET_MOUNTED_LAST_NFS_SHARES % self.storage[position].conf
            cmd += print_cmd
            res = self._run_cmd(self.clouds[position], cmd)
            res = set(res if isinstance(res, list) else [res])
        if not res:
            raise exception.AbortMigrationError(
                'No NFS share found on "%s"' % position)
        return res

    def mount_dirs(self, position, vt=None):
        """
        Get shares from mount output.

        :return: list of paths

        """
        return self._mount_output(position, vt=vt, dirs_only=True)

    def _vt_map(self):
        # host volume_type_id->hostname map
        # cached property
        if self.dst_volume_types is None:
            self.dst_volume_types = _volume_types_map(self.data[DST])
        res = dict(
            [(vt['id'], self.dst_volume_types[vt['name']])
             for vt in _volume_types(self.data[SRC])
             if vt['name'] in self.dst_volume_types])
        return res

    def _dst_host(self, vtid=None):
        # vtid -> dst_host
        # cached property
        if self.dst_hosts is None:
            self.dst_hosts = \
                [i.host for i in
                 self.clouds[DST][RES].cinder_client.services.list(
                     binary=CINDER_VOLUME) if i.state == 'up']
        # cached property
        if self.dst_volume_types is None:
            self.dst_volume_types = _volume_types_map(self.data[DST])

        host_map = {}
        for h in self.dst_hosts:
            if '@' in h:
                _, t = h.split('@')
                if t in self.dst_volume_types:
                    host_map[self.dst_volume_types[t]] = h

        host = host_map.get(vtid, self.dst_hosts[0])
        return host

    def _dst_mount_info(self):
        # cached property
        if self.dst_mount is None:
            self.dst_mount = {}
            if not _volume_types(self.data[DST]):
                self.dst_mount[DEFAULT] = set([
                    tuple(line.split(MOUNT_DELIM))
                    for line in self._mount_output(DST)
                    if line
                ])
            for vt in _volume_types(self.data[DST]):
                self.dst_mount[vt['id']] = set([])
                output = self._mount_output(DST, vt=vt)
                for line in output:
                    if line:
                        self.dst_mount[vt['id']].add(
                            tuple(line.split(MOUNT_DELIM)))

        return self.dst_mount

    def _dir_to_provider(self, dst):
        # cached property
        if self.dst_dir_to_provider is None:
            mount_info = self._dst_mount_info()
            if _volume_types(self.data[DST]):
                self.dst_dir_to_provider = \
                    dict([t for vt in self.data[DST]['volume_types']
                          for t in mount_info[vt['id']]])
            else:
                self.dst_dir_to_provider = \
                    dict([t for t in mount_info[DEFAULT]])

        return self.dst_dir_to_provider[dst]

    def _provider_to_vtid(self, provider):
        # cached property
        if self.dst_provider_to_vtid is None:
            mount_info = self._dst_mount_info()
            if _volume_types(self.data[DST]):
                self.dst_provider_to_vtid = \
                    dict([(t[1], vt['id'])
                          for vt in self.data[DST]['volume_types']
                          for t in mount_info[vt['id']]])
            else:
                self.dst_provider_to_vtid = \
                    dict([(t[1], None) for t in mount_info[DEFAULT]])
        return self.dst_provider_to_vtid[provider]

    def _path_map(self):
        paths = {SRC: {'all': set([])}, DST: {'all': set([])}}
        paths[SRC][BY_VTID] = {}

        if not _volume_types(self.data[SRC]):
            paths[SRC][ALL] = self.mount_dirs(SRC)

        for vt in _volume_types(self.data[SRC]):
            paths[SRC][BY_VTID][vt['id']] = self.mount_dirs(SRC, vt)

        paths[DST][BY_VTID] = {}
        mount_info = self._dst_mount_info()

        if not _volume_types(self.data[DST]):
            for t in mount_info.get(DEFAULT):
                paths[DST][ALL].add(t[0])

        for vt in _volume_types(self.data[DST]):
            paths[DST][BY_VTID][vt['id']] = set(
                t[0] for t in mount_info[vt['id']])

        for i in self.clouds:
            for sd in sorted(paths[i][BY_VTID].values()):
                paths[i][ALL].update(sd)

        return paths

    def _paths(self, position, vtid=None):
        # cached property
        if self.path_map is None:
            self.path_map = self._path_map()
        if vtid:
            res = self.path_map[position][BY_VTID][vtid]
            if res:
                return res
        return self.path_map[position][ALL]

    def _volumes_size_map(self):
        LOG.info('Calculate size of each volume.')
        volumes_size_map = {}
        for position in self.clouds:
            for v in self.data[position]['volumes']:
                LOG.debug('Calculating size of volume %s on %s cloud',
                          v['id'], position)
                volume_type_id = v.get('volume_type_id', None)
                srcpaths = self._paths(position, volume_type_id)
                src = self.find_dir(position, srcpaths, v)
                vol_size = self.volume_size(self.clouds[position], src)
                volumes_size_map[v['id']] = vol_size

                LOG.info('Volume %s(%s) size is %s.',
                         v.get('display_name', ''),
                         v['id'],
                         sizeof_format.sizeof_fmt(vol_size))
        return volumes_size_map

    def _try_copy_volumes(self):
        vt_map = self._vt_map()

        failed = []

        volumes_size_map = self._volumes_size_map()
        view = cinder_storage_view.CinderStorageMigrationProgressView(
            self.data[SRC]['volumes'],
            self.data[DST]['volumes'],
            volumes_size_map
        )

        view.show_stats()
        for v in self.data[SRC]['volumes']:
            LOG.info('Start migrate volume %s(%s)',
                     v.get('display_name', ''), v['id'])

            volume_type_id = v.get('volume_type_id', None)
            srcpaths = self._paths(SRC, volume_type_id)
            LOG.debug('srcpaths: %s', str(srcpaths))

            if volume_type_id in vt_map:
                # src -> dst
                v['volume_type_id'] = vt_map.get(volume_type_id, None)
            else:
                v['volume_type_id'] = None
            LOG.debug('Vt map: %s', str(vt_map))

            dstpaths = self._paths(DST, v['volume_type_id'])
            if not dstpaths:
                err_msg = 'No mount found on DST Cloud'
                if v['volume_type_id']:
                    err_msg += ' for volume type: %s' % v['volume_type_id']
                raise exception.AbortMigrationError(err_msg)

            LOG.debug('dstpaths: %s', str(dstpaths))

            src = self.find_dir(SRC, srcpaths, v)
            if not src:
                raise exception.AbortMigrationError(
                    'No SRC volume file found for %s[%s]'
                    % (v.get('display_name', None), v['id']))
            dst, elapsed_time = self._transfer(src, dstpaths, v,
                                               volumes_size_map[v['id']])

            if dst:
                v['provider_location'] = self._dir_to_provider(dst)
                vtid = self._provider_to_vtid(v['provider_location'])
                v[HOST] = self._dst_host(vtid)
                view.sync_migrated_volumes_info(v, elapsed_time)
            else:
                failed.append(v)
                view.sync_failed_volumes_info(v)

            view.show_progress()

        if failed:
            LOG.error(
                'Migration failed for volumes: %s',
                ', '.join([
                    "%s(%s)" % (v['display_name'], v['id'])
                    for v in failed])
            )
            self.data[SRC]['volumes'] = [
                v for v in self.data[SRC]['volumes'] if v not in failed
            ]

        return failed
