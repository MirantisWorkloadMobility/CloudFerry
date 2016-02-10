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


from itertools import ifilter

from cinderclient.v1 import client as cinder_client
from cinderclient import exceptions as cinder_exc
from pymysql import cursors

from cloudferrylib.base import storage
from cloudferrylib.os.storage import filters as cinder_filters
from cloudferrylib.utils import filters
from cloudferrylib.utils import log
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import utils as utl

import re

RE_EXTRACT_HOST = re.compile(r'//([^:^/]*)')

AVAILABLE = 'available'
IN_USE = "in-use"
CINDER_VOLUME = "cinder-volume"
LOG = log.getLogger(__name__)
ID = 'id'
DISPLAY_NAME = 'display_name'
PROJECT_ID = 'project_id'
STATUS = 'status'
TENANT_ID = 'tenant_id'
USER_ID = 'user_id'
DELETED = 'deleted'
HOST = 'host'
IGNORED_TBL_LIST = ('quotas', 'quota_usages')
QUOTA_TABLES = (
    'quotas',
    'quota_classes',
    'quota_usages',
)
SRC = 'src'
TABLE_UNIQ_KEYS = {
    'volumes': ['id'],
    'quotas': ['project_id', 'resource'],
    'quota_classes': ['class_name', 'resource'],
    'quota_usages': ['project_id', 'resource'],
    'reservations': ['project_id', 'resource', 'usage_id'],
    'volume_metadata': ['volume_id', 'key'],
    'volume_glance_metadata': ['volume_id', 'snapshot_id', 'key'],
}

VALID_STATUSES = ['available', 'in-use', 'attaching', 'detaching']


class CinderStorage(storage.Storage):

    """ The main class for working with Openstack cinder client.

    to use this strategy - specify cinder_migration_strategy in config as
    'cloudferrylib.os.storage.cinder.CinderStorage'

    """

    def __init__(self, config, cloud):
        super(CinderStorage, self).__init__(config)
        self.ssh_host = config.cloud.ssh_host
        self.mysql_host = config.mysql.db_host \
            if config.mysql.db_host else self.ssh_host
        self.cloud = cloud
        self.identity_client = cloud.resources[utl.IDENTITY_RESOURCE]
        self.mysql_connector = cloud.mysql_connector('cinder')
        self.volume_filter = None

    @property
    def cinder_client(self):
        return self.proxy(self.get_client(self.config), self.config)

    def get_client(self, params=None, tenant=None):
        params = params or self.config

        return cinder_client.Client(
            params.cloud.user,
            params.cloud.password,
            tenant or params.cloud.tenant,
            params.cloud.auth_url,
            cacert=params.cloud.cacert,
            insecure=params.cloud.insecure,
            region_name=params.cloud.region
        )

    def get_filter(self):
        if self.volume_filter is None:
            with open(self.config.migrate.filter_path, 'r') as f:
                filter_yaml = filters.FilterYaml(f)
                filter_yaml.read()

            self.volume_filter = cinder_filters.CinderFilters(
                self.cinder_client, filter_yaml)

        return self.volume_filter

    def read_info(self, **kwargs):
        info = {utl.VOLUMES_TYPE: {}}
        for vol in self.get_volumes_list(search_opts=kwargs):
            volume = self.convert_volume(vol, self.config, self.cloud)
            snapshots = {}
            if self.config.migrate.keep_volume_snapshots:
                search_opts = {'volume_id': volume['id']}
                for snap in self.get_snapshots_list(search_opts=search_opts):
                    snapshot = self.convert_snapshot(snap,
                                                     volume,
                                                     self.config,
                                                     self.cloud)
                    snapshots[snapshot['id']] = snapshot
            info[utl.VOLUMES_TYPE][vol.id] = {utl.VOLUME_BODY: volume,
                                              'snapshots': snapshots,
                                              utl.META_INFO: {
                                              }}
        if self.config.migrate.keep_volume_storage:
            info['volumes_db'] = {utl.VOLUMES_TYPE: '/tmp/volumes'}

            # cleanup db
            self.cloud.ssh_util.execute('rm -rf /tmp/volumes',
                                        host_exec=self.mysql_host)

            for table_name, file_name in info['volumes_db'].iteritems():
                self.download_table_from_db_to_file(table_name, file_name)
        return info

    def deploy(self, info):
        if info.get('volumes_db'):
            return self.deploy_volumes_db(info)
        return self.deploy_volumes(info)

    def attach_volume_to_instance(self, volume_info):
        if 'instance' in volume_info[utl.META_INFO]:
            if volume_info[utl.META_INFO]['instance']:
                self.attach_volume(
                    volume_info[utl.VOLUME_BODY]['id'],
                    volume_info[utl.META_INFO]['instance']['instance']['id'],
                    volume_info[utl.VOLUME_BODY]['device'])

    def filter_volumes(self, volumes):
        filtering_enabled = self.cloud.position == SRC

        if filtering_enabled:
            flts = self.get_filter().get_filters()
            for f in flts:
                volumes = ifilter(f, volumes)
            volumes = [i for i in volumes]

            def get_name(volume):
                if isinstance(volume, dict):
                    return volume.get(DISPLAY_NAME, volume['id'])
                return getattr(volume, DISPLAY_NAME, None) or volume.id

            LOG.info("Filtered volumes: %s",
                     ", ".join((str(get_name(i)) for i in volumes)))
        return volumes

    def get_volumes_list(self, detailed=True, search_opts=None):
        search_opts['all_tenants'] = 1
        volumes = self.cinder_client.volumes.list(detailed, search_opts)

        volumes = self.filter_volumes(volumes)

        return volumes

    def get_snapshots_list(self, detailed=True, search_opts=None):
        return self.cinder_client.volume_snapshots.list(detailed, search_opts)

    def create_snapshot(self, volume_id, force=False,
                        display_name=None, display_description=None):
        return self.cinder_client.volume_snapshots.create(volume_id,
                                                          force,
                                                          display_name,
                                                          display_description)

    def create_volume(self, size, **kwargs):
        return self.cinder_client.volumes.create(size, **kwargs)

    def delete_volume(self, volume_id):
        volume = self.get_volume_by_id(volume_id)
        self.cinder_client.volumes.delete(volume)

    def get_volume_by_id(self, volume_id):
        return self.cinder_client.volumes.get(volume_id)

    def update_volume(self, volume_id, **kwargs):
        volume = self.get_volume_by_id(volume_id)
        return self.cinder_client.volumes.update(volume, **kwargs)

    def attach_volume(self, volume_id, instance_id, mountpoint, mode='rw'):
        volume = self.get_volume_by_id(volume_id)
        return self.cinder_client.volumes.attach(volume,
                                                 instance_uuid=instance_id,
                                                 mountpoint=mountpoint,
                                                 mode=mode)

    def detach_volume(self, volume_id):
        return self.cinder_client.volumes.detach(volume_id)

    def finish(self, vol):
        try:
            with proxy_client.expect_exception(cinder_exc.BadRequest):
                self.cinder_client.volumes.set_bootable(
                    vol[utl.VOLUME_BODY]['id'],
                    vol[utl.VOLUME_BODY]['bootable'])
        except cinder_exc.BadRequest:
            LOG.info("Can't update bootable flag of volume with id = %s "
                     "using API, trying to use DB...",
                     vol[utl.VOLUME_BODY]['id'])
            self.__patch_option_bootable_of_volume(
                vol[utl.VOLUME_BODY]['id'],
                vol[utl.VOLUME_BODY]['bootable'])

    def upload_volume_to_image(self, volume_id, force, image_name,
                               container_format, disk_format):
        volume = self.get_volume_by_id(volume_id)
        resp, image = self.cinder_client.volumes.upload_to_image(
            volume=volume,
            force=force,
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format)
        return resp, image['os-volume_upload_image']['image_id']

    def get_status(self, resource_id):
        return self.cinder_client.volumes.get(resource_id).status

    def deploy_volumes(self, info):
        new_ids = {}
        for vol_id, vol in info[utl.VOLUMES_TYPE].iteritems():
            vol_for_deploy = self.convert_to_params(vol)
            volume = self.create_volume(**vol_for_deploy)
            vol[utl.VOLUME_BODY]['id'] = volume.id
            self.try_wait_for_status(volume.id, self.get_status, AVAILABLE)
            self.finish(vol)
            new_ids[volume.id] = vol_id
        return new_ids

    def deploy_volumes_db(self, info):
        for table_name, file_name in info['volumes_db'].iteritems():
            self.upload_table_to_db(table_name, file_name)
        for tenant in info['tenants']:
            self.update_column_with_condition('volumes',
                                              'project_id',
                                              tenant['tenant']['id'],
                                              tenant[utl.META_INFO]['new_id'])
        for user in info['users']:
            self.update_column_with_condition('volumes', 'user_id',
                                              user['user']['id'],
                                              user[utl.META_INFO]['new_id'])
        self.update_column_with_condition('volumes', 'attach_status',
                                          'attached', 'detached')
        self.update_column_with_condition('volumes', 'status', 'in-use',
                                          'available')
        self.update_column('volumes', 'instance_uuid', 'NULL')
        return {}

    @staticmethod
    def convert_volume(vol, cfg, cloud):
        compute = cloud.resources[utl.COMPUTE_RESOURCE]
        volume = {
            'id': vol.id,
            'size': vol.size,
            'display_name': vol.display_name,
            'display_description': vol.display_description,
            'volume_type': (
                None if vol.volume_type == u'None' else vol.volume_type),
            'availability_zone': vol.availability_zone,
            'device': vol.attachments[0][
                'device'] if vol.attachments else None,
            'bootable': False,
            'volume_image_metadata': {},
            'host': None,
            'path': None
        }
        if 'bootable' in vol.__dict__:
            volume[
                'bootable'] = True if vol.bootable.lower() == 'true' else False
        if 'volume_image_metadata' in vol.__dict__:
            volume['volume_image_metadata'] = {
                'image_id': vol.volume_image_metadata['image_id'],
                'checksum': vol.volume_image_metadata['checksum']
            }
        if cfg.storage.backend == utl.CEPH:
            volume['path'] = "%s/%s%s" % (
                cfg.storage.rbd_pool, cfg.storage.volume_name_template, vol.id)
            volume['host'] = (cfg.storage.host
                              if cfg.storage.host
                              else cfg.cloud.ssh_host)
        elif vol.attachments and (cfg.storage.backend == utl.ISCSI):
            instance = compute.read_info(
                search_opts={'id': vol.attachments[0]['server_id']})
            instance = instance[utl.INSTANCES_TYPE]
            instance_info = instance.values()[0][utl.INSTANCE_BODY]
            volume['host'] = instance_info['host']
            list_disk = utl.get_libvirt_block_info(
                instance_info['instance_name'],
                cfg.cloud.ssh_host,
                instance_info['host'],
                cfg.cloud.ssh_user,
                cfg.cloud.ssh_sudo_password)
            volume['path'] = utl.find_element_by_in(list_disk, vol.id)
        return volume

    @staticmethod
    def convert_snapshot(snap, volume, cfg, cloud):

        snapshot = {
            'id': snap.id,
            'volume_id': snap.volume_id,
            'tenant_id': snap.project_id,
            'display_name': snap.display_name,
            'display_description': snap.display_description,
            'created_at': snap.created_at,
            'size': snap.size,
            'vol_path': volume['path']
        }

        if cfg.storage.backend == utl.CEPH:
            snapshot['name'] = "%s%s" % (cfg.storage.snapshot_name_template,
                                         snap.id)
            snapshot['path'] = "%s@%s" % (snapshot['vol_path'],
                                          snapshot['name'])
            snapshot['host'] = (cfg.storage.host
                                if cfg.storage.host
                                else cfg.cloud.ssh_host)

        return snapshot

    @staticmethod
    def convert_to_params(vol):
        info = {
            'size': vol[utl.VOLUME_BODY]['size'],
            'display_name': vol[utl.VOLUME_BODY]['display_name'],
            'display_description': vol[utl.VOLUME_BODY]['display_description'],
            'volume_type': vol[utl.VOLUME_BODY]['volume_type'],
            'availability_zone': vol[utl.VOLUME_BODY]['availability_zone'],
        }
        if 'image' in vol[utl.META_INFO]:
            if vol[utl.META_INFO]['image']:
                info['imageRef'] = vol[utl.META_INFO]['image']['id']
        return info

    def __patch_option_bootable_of_volume(self, volume_id, bootable):
        cmd = ('UPDATE volumes SET volumes.bootable=%s WHERE '
               'volumes.id="%s"') % (int(bootable), volume_id)
        self.mysql_connector.execute(cmd)

    def download_table_from_db_to_file(self, table_name, file_name):
        self.mysql_connector.execute("SELECT * FROM %s INTO OUTFILE '%s';" %
                                     (table_name, file_name))

    def upload_table_to_db(self, table_name, file_name):
        self.mysql_connector.execute("LOAD DATA INFILE '%s' INTO TABLE %s" %
                                     (file_name, table_name))

    def update_column_with_condition(self, table_name, column,
                                     old_value, new_value):

        self.mysql_connector.execute("UPDATE %s SET %s='%s' WHERE %s='%s'" %
                                     (table_name, column, new_value, column,
                                         old_value))

    def update_column(self, table_name, column_name, new_value):
        self.mysql_connector.execute("UPDATE %s SET %s='%s'" %
                                     (table_name, column_name, new_value))

    def get_volume_path_iscsi(self, vol_id):
        cmd = "SELECT provider_location FROM volumes WHERE id='%s';" % vol_id

        result = self.cloud.mysql_connector.execute(cmd)

        if not result:
            raise Exception('There is no such raw in Cinder DB with the '
                            'specified volume_id=%s' % vol_id)

        provider_location = result.fetchone()[0]
        provider_location_list = provider_location.split()

        iscsi_target_id = provider_location_list[1]
        lun = provider_location_list[2]
        ip = provider_location_list[0].split(',')[0]

        volume_path = '/dev/disk/by-path/ip-%s-iscsi-%s-lun-%s' % (
            ip,
            iscsi_target_id,
            lun)

        return volume_path


def skip_invalid_status_volumes(volumes):
    result = []
    for v in volumes:
        if v[STATUS] not in VALID_STATUSES:
            LOG.warning('Skipping volume %s[%s] in "%s" state',
                        v.get(DISPLAY_NAME, ''), v[ID], v[STATUS])
        else:
            result.append(v)
    return result


class CinderNFSStorage(CinderStorage):

    """Migration strategy used with NFS multi backend.

    copies volume files via rsync;
    copies data directly from database to database, avoiding creation of
    new volumes;

    To use this strategy - specify cinder_migration_strategy in config as
    'cloudferrylib.os.storage.cinder.CinderNFSStorage'.

    """

    def __init__(self, config, cloud):
        super(CinderNFSStorage, self).__init__(config, cloud)
        self.list_of_tables = [
            'volumes',
            'quotas',
            'quota_classes',
            'volume_types',
            'volume_type_extra_specs',
            'volume_metadata',
            'volume_glance_metadata',
        ]

    def get_client(self, params=None):
        params = params or self.config

        return cinder_client.Client(
            params.cloud.user,
            params.cloud.password,
            params.cloud.tenant,
            params.cloud.auth_url,
            cacert=params.cloud.cacert,
            insecure=params.cloud.insecure,
            region_name=params.cloud.region
        )

    def _filter_quotas_list(self, table_name, quotas):
        filtering_enabled = self.cloud.position == SRC

        if filtering_enabled:
            fltr = self.get_filter().get_tenant_filter()
            quotas = [q for q in quotas if fltr(q)]
            LOG.info("Filtered %s: %s", table_name,
                     ", ".join((str(v) for v in quotas)))
        return quotas

    def _filter(self, table, result):
        if table == 'volumes':
            result = self.filter_volumes(result)
            result = skip_invalid_status_volumes(result)
        if table in QUOTA_TABLES:
            result = self._filter_quotas_list(table, result)
        return result

    def read_db_info(self, **kwargs):
        info = {}
        for table in self.list_of_tables:
            data = CinderTable(self.cloud.mysql_connector('cinder'),
                               table).read_info(**kwargs)
            # filter deleted volumes
            data = [a for a in data if not a.get(DELETED, 0)]

            if self.cloud.position == SRC:
                data = self._filter(table, data)
                migrated = self.cloud.migration
                for e in data:
                    for col in PROJECT_ID, TENANT_ID:
                        if col in e:
                            e[col] = migrated[utl.IDENTITY_RESOURCE].\
                                migrated_id(e[col], resource_type='tenants')
                        if USER_ID in e:
                            e[USER_ID] = migrated[utl.IDENTITY_RESOURCE].\
                                migrated_id(e[USER_ID], resource_type='users')
            info[table] = data
        return info

    def reread(self):
        """Re-read db info after deployment.

        :return: dict

        """
        return self.read_db_info()

    def deploy_data_to_table(self, table_name, data):
        if not data:
            # if we don't have data to be added - exit
            return

        CinderTable(self.cloud.mysql_connector('cinder'),
                    table_name).deploy(data)

    def deploy(self, data):
        """ Read data and writes it to database.

        :return: data

        """
        for table_name in self.list_of_tables:
            if table_name in data:
                self.deploy_data_to_table(table_name, data[table_name])
        return data


class CinderTable(object):

    """Cinder DB table."""

    def __init__(self, connector, table_name):
        self.mysql_connector = connector
        self.table_name = table_name
        self.keys = TABLE_UNIQ_KEYS.get(table_name, ['id'])

    def write_to_database(self, cmd, cursor, entries, primary_key=None):
        if not entries:
            return
        cmd = cmd.upper()

        for entry in entries:
            if 'snapshot_id' in entry:
                entry.pop('snapshot_id')
            keys = entry.keys()
            values = tuple([entry[k] for k in keys])

            reserved = ['key']
            for key in reserved:
                if key in keys:
                    keys[keys.index(key)] = '%s.%s' % (self.table_name, key)

            if cmd == 'UPDATE':
                query = (
                    "UPDATE %s SET %s WHERE %s='%s'" % (
                        self.table_name,
                        ",".join(k + "=%s" for k in keys),
                        primary_key,
                        entry[primary_key],
                    )
                )
            elif cmd == 'INSERT':
                query = (
                    "INSERT INTO %s (%s) VALUES (%s)" % (
                        self.table_name,
                        ",".join(keys),
                        ",".join(["%s" for _ in keys]),
                    )
                )
            else:
                raise ValueError('Unknown command: %s', cmd)

            LOG.debug(query, *values)
            cursor.execute(query, values)

    def get_primary_key(self, cursor):
        cursor.execute("show index from %s where Key_name = 'PRIMARY'" %
                       self.table_name)
        primary_key = cursor.fetchone().get("Column_name")
        LOG.debug("Primary key of %s: %s", self.table_name, primary_key)
        return primary_key

    def get_auto_increment(self, cursor):
        cursor.execute(("select auto_increment from information_schema.tables "
                        "where table_name = '%s' "
                        "and table_schema = 'cinder'") % self.table_name)
        auto_increment = cursor.fetchone().get("auto_increment")
        LOG.debug("Auto increment of %s: %s", self.table_name, auto_increment)
        return auto_increment

    @staticmethod
    def identical(obj1, obj2):
        common_cols = list(set(obj1.keys()) & set(obj2.keys()))

        def common(obj):
            return {i: obj[i] for i in obj if i in common_cols}

        return common(obj1) == common(obj2)

    def mul_key(self, row):
        """Get MUL key for row.

        :return: list

        """
        return tuple([row.get(key, None) for key in self.keys])

    def filter_data(self, existing_data, data_to_be_added, primary_key,
                    auto_increment):
        """ Handle duplicates in database.

        :return: (entries, duplicates)

        """
        entries, duplicates = [], []

        existing = {self.mul_key(i): i for i in existing_data}
        for candidate in data_to_be_added:
            pk = candidate[primary_key]
            key = self.mul_key(candidate)
            if auto_increment or primary_key not in self.keys:
                candidate.pop(primary_key)
            if key in existing:
                ex = existing[key]
                if self.identical(ex, candidate):
                    # if dicts are comlpletely same - drop that dict
                    LOG.debug("Duplicate in table %s for pk %s",
                              self.table_name, pk)
                else:
                    LOG.warning("Duplicate in table %s: %s", self.table_name,
                                str(ex))
                    LOG.warning("Candidate to update %s: %s", self.table_name,
                                str(candidate))
                    candidate[primary_key] = pk
                    duplicates.append(candidate)
            else:
                entries.append(candidate)
        return (entries, duplicates)

    def deploy(self, data):
        sql_engine = self.mysql_connector.get_engine()
        connection = sql_engine.raw_connection()
        cursor = connection.cursor(cursors.DictCursor)

        primary_key = self.get_primary_key(cursor)
        auto_increment = self.get_auto_increment(cursor)
        data_in_database = self.read_info()
        entries, duplicates = self.filter_data(data_in_database, data,
                                               primary_key, auto_increment)

        self.write_to_database("INSERT", cursor, entries)
        self.write_to_database("UPDATE", cursor, duplicates, primary_key)

        cursor.close()
        connection.commit()
        connection.close()

    def select_all(self, table_name):
        """Select * from table.

        :return: query

        """
        sql = ("SELECT * from %s" % table_name)
        return self.mysql_connector.execute(sql)

    def get_table(self):
        query = self.select_all(self.table_name)
        column_names = query.keys()
        result = [dict(zip(column_names, row)) for row in query]
        return result

    def read_info(self, **kwargs):
        """ Perform SQL query and returns rows as dict. """
        # ignore deleted and errored volumes
        result = self.get_table()
        if not result:
            return result
        if kwargs:
            result = [a for a in result
                      for k, v in kwargs.items()
                      if a.get(k, None) == v]
        for r in result:
            if DELETED in r and not r.get(DELETED):
                r[DELETED] = 0
        return result
