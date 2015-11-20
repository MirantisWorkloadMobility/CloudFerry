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
from cloudferrylib.base.action import action
from cloudferrylib.base.exception import AbortMigrationError
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import utils
from fabric.context_managers import settings

import jsondate
import os

LOG = utils.get_log(__name__)

NAMESPACE_CINDER_CONST = "cinder_database"

CINDER_VOLUME = "cinder-volume"
HOST = 'host'
BY_VTID = 'by_vtid'
ALL = 'all'
MOUNT_DELIM = '='
DEFAULT = 'default'
SRC = 'src'
DST = 'dst'
CLOUD = 'cloud'
RES = 'res'
CFG = 'cfg'

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

RSYNC_CMD = (
    'rsync --progress --append -a --no-owner --no-group'
    ' -e "ssh -o StrictHostKeyChecking=no"'
)


def _remote_runner(cloud):
    return remote_runner.RemoteRunner(cloud[CFG].get(HOST),
                                      cloud[CFG].ssh_user,
                                      cloud[CFG].ssh_sudo_password,
                                      sudo=True)


def _volume_types_map(data):
    return dict([(t['name'], t['id']) for t in data.get('volume_types', [])])


def _volume_types(data):
    return data.get('volume_types', [])


def _modify_data(data):
    for volume in data['volumes']:
        if volume.get('status', '') == 'in-use':
            volume['mountpoint'] = None
            volume['status'] = 'available'
            volume['instance_uuid'] = None
            volume['attach_status'] = 'detached'

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
            raise AbortMigrationError(
                "No resource {res} found".format(res=utils.STORAGE_RESOURCE))
        return cinder_resource


class GetVolumesDb(CinderDatabaseInteraction):

    """Retrieve Db info."""

    def run(self, *args, **kwargs):
        """
        Run GetVolumesDb action.

        :return: namespace with db info

        """
        search_opts = kwargs.get('search_opts_tenant', {})
        return {NAMESPACE_CINDER_CONST:
                self.get_resource().read_db_info(**search_opts)}


class WriteVolumesDb(CinderDatabaseInteraction):

    """
    Copy volumes' data on nfs backends.

    Work via rsync, can handle big files
    and resume after errors.
    Depends on 'GetVolumesDb' action, it must be run first.

    """

    def __init__(self, *args, **kwargs):
        super(WriteVolumesDb, self).__init__(*args, **kwargs)

        self.ssh_attempts = self.cfg.migrate.ssh_connection_attempts
        self.storage = {
            SRC: self.cfg.src_storage,
            DST: self.cfg.dst_storage,
        }

        self.data = {SRC: {}, DST: {}}

        self.dst_hosts = None
        self.dst_mount = None
        self.dst_dir_to_provider = None
        self.dst_provider_to_vtid = None
        self.dst_volume_types = None
        self.path_map = None
        self.mount_all = {}

    def run(self, *args, **kwargs):
        """Run WriteVolumesDb Action."""
        data_from_namespace = kwargs.get(NAMESPACE_CINDER_CONST)
        if not data_from_namespace:
            raise AbortMigrationError(
                "Cannot read attribute {attribute} from namespace".format(
                    attribute=NAMESPACE_CINDER_CONST))

        self.cloud = {
            SRC: {
                CLOUD: self.src_cloud,
                RES: self.src_cloud.resources.get(utils.STORAGE_RESOURCE),
                CFG: self.cfg.src,
            },
            DST: {
                CLOUD: self.dst_cloud,
                RES: self.dst_cloud.resources.get(utils.STORAGE_RESOURCE),
                CFG: self.cfg.dst,
            }
        }

        self.data[SRC] = jsondate.loads(data_from_namespace)

        search_opts = kwargs.get('search_opts_tenant', {})
        self.data[DST] = jsondate.loads(
            self.cloud[DST][RES].read_db_info(**search_opts))

        LOG.debug('Cloud info: %s', str(self.cloud))

        self._copy_volumes()

        self.data[SRC] = _modify_data(self.data[SRC])
        self.cloud[DST][RES].deploy(jsondate.dumps(self.data[SRC]))

    def _run_cmd(self, cloud, cmd):
        runner = _remote_runner(cloud)
        with settings(gateway=cloud[CLOUD].getIpSsh(),
                      connection_attempts=self.ssh_attempts):
            output = runner.run(cmd)
            res = output.split('\r\n')
            return res if len(res) > 1 else res[0]

    def run_repeat_on_errors(self, cloud, cmd):
        """Run remote command cmd."""
        runner = _remote_runner(cloud)
        with settings(gateway=cloud[CLOUD].getIpSsh(),
                      connection_attempts=self.ssh_attempts):
            runner.run_repeat_on_errors(cmd)

    def find_dir(self, position, paths, v):
        """
        Find file v in paths.

        :return: path to the file

        """
        if not paths:
            return None
        volume_filename = self.storage[position].volume_name_template + v['id']
        for p in paths:
            cmd = 'ls -1 %s' % p
            lst = self._run_cmd(self.cloud[position], cmd)
            if lst and not isinstance(lst, list):
                lst = [lst]
            if volume_filename in lst:
                return '%s/%s' % (p, volume_filename)

    def _run_rsync(self, src, dst):
        cmd = RSYNC_CMD
        cmd += ' %s %s@%s:%s' % (src, self.cloud[DST][CFG].ssh_user,
                                 self.cloud[DST][CFG].get(HOST), dst)
        self.run_repeat_on_errors(self.cloud[SRC], cmd)

    def volume_size(self, cloud, vol_file):
        """
        Get size of vol_file in bytes.

        :return: int

        """
        cmd = (
            "du -b %s | awk '{print $1}'"
        ) % vol_file
        size = self._run_cmd(cloud, cmd)
        return int(size)

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
        LOG.debug("Cleaning %s", filepath)
        self.run_repeat_on_errors(cloud, cmd)

    def _rsync_if_enough_space(self, src_size, src, dst):
        dst_free_space = self.free_space(self.cloud[DST], dst)
        if dst_free_space > src_size:
            LOG.debug("Enough space found on %s", dst)
            self._run_rsync(src, dst)
            return True
        LOG.debug("No enough space on %s", dst)

    def checksum(self, position, filepath):
        """
        Get checksum of `filepath`.

        :return: str

        """
        cmd = (
            "md5sum %s | awk '{print $1}'"
        ) % filepath
        return self._run_cmd(self.cloud[position], cmd)

    def _rsync(self, src, dstpaths, volume):
        LOG.debug("Trying rsync file for volume: %s[%s]",
                  volume.get('display_name', None), volume['id'])
        dstfile = self.find_dir(DST, dstpaths, volume)
        src_size = self.volume_size(self.cloud[SRC], src)
        LOG.debug("Source file size = %d", src_size)
        LOG.debug("Searching for space for volume: %s[%s]",
                  volume.get('display_name', None), volume['id'])
        if dstfile:
            LOG.debug("File found on destination: %s", dstfile)
            dst_size = self.volume_size(self.cloud[DST], dstfile)
            LOG.debug("Destination file size = %d", dst_size)
            dst = os.path.dirname(dstfile)
            if self.checksum(SRC, src) == self.checksum(DST, dstfile):
                LOG.debug("Destination file is up-to-date")
                return dst
            if self._rsync_if_enough_space(src_size, src, dst):
                return dst
            else:
                self._clean(self.cloud[DST], dstfile)

        for dst in dstpaths:
            res = self._rsync_if_enough_space(src_size, src, dst)
            if res:
                return dst
        raise AbortMigrationError('No space found for %s on %s' % (
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
        backend_blocks = self._run_cmd(self.cloud[position], cmd)
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
            backend = self._run_cmd(self.cloud[position], cmd)

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
            nfs_shares = self._run_cmd(self.cloud[position], cmd)
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
            res = self._run_cmd(self.cloud[position], cmd)
            res = set(res if isinstance(res, list) else [res])
        if not res:
            raise AbortMigrationError('No NFS share found on "%s"' % position)
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
                 self.cloud[DST][RES].cinder_client.services.list(
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
                ])
            for vt in _volume_types(self.data[DST]):
                self.dst_mount[vt['id']] = set([])
                output = self._mount_output(DST, vt=vt)
                for line in output:
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

        for i in self.cloud:
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

    def _copy_volumes(self):
        vt_map = self._vt_map()

        for v in self.data[SRC]['volumes']:
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
            LOG.debug('dstpaths: %s', str(dstpaths))

            src = self.find_dir(SRC, srcpaths, v)
            if not src:
                raise AbortMigrationError(
                    'No SRC volume file found for %s[%s]'
                    % (v.get('display_name', None), v['id']))
            LOG.debug('SRC volume file: %s', str(src))
            dst = self._rsync(src, dstpaths, v)

            v['provider_location'] = self._dir_to_provider(dst)
            vtid = self._provider_to_vtid(v['provider_location'])
            v[HOST] = self._dst_host(vtid)
