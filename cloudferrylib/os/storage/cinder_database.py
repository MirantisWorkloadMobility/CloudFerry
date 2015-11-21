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


import jsondate
from cinderclient.v1 import client as cinder_client
from cloudferrylib.utils import utils as utl
from cloudferrylib.os.storage import cinder_storage
from cloudferrylib.os.storage import filters as cinder_filters
from cloudferrylib.utils import filters

CINDER_VOLUME = "cinder-volume"
LOG = utl.get_log(__name__)
PROJECT_ID = 'project_id'
STATUS = 'status'
TENANT_ID = 'tenant_id'
USER_ID = 'user_id'
DELETED = 'deleted'
HOST = 'host'
IGNORED_TBL_LIST = ('quota_usages')
QUOTA_TABLES = (
    'quotas',
    'quota_classes',
    'quota_usages',
)


class CinderStorage(cinder_storage.CinderStorage):

    """Migration strategy used with NFS backend

    copies data directly from database to database, avoiding creation of
    new volumes

    to use this strategy - specify cinder_migration_strategy in config as
    'cloudferrylib.os.storage.cinder_database.CinderStorage'

    """

    def __init__(self, config, cloud):
        self.config = config
        self.cloud = cloud
        self._volume_filter = None
        self.table = None
        self.hosts = None
        self.host_counter = 0
        self.identity_client = cloud.resources['identity']
        # FIXME This class holds logic for all these tables. These must be
        # split into separate classes
        self.list_of_tables = [
            'volumes',
            'quotas',
            'quota_classes',
            'quota_usages',
            'reservations',
            'volume_types',
            'volume_type_extra_specs',
        ]
        super(CinderStorage, self).__init__(config, cloud)

    def _get_volume_filter(self):
        if self._volume_filter is None:
            with open(self.config.migrate.filter_path, 'r') as f:
                filter_yaml = filters.FilterYaml(f)
                filter_yaml.read()

            self._volume_filter = cinder_filters.CinderFilters(
                self.cinder_client, filter_yaml)

        return self._volume_filter

    def get_client(self, params=None):

        params = self.config if not params else params
        return cinder_client.Client(
            params.cloud.user,
            params.cloud.password,
            params.cloud.tenant,
            params.cloud.auth_url,
            cacert=self.config.cloud.cacert,
            insecure=self.config.cloud.insecure)

    def _check_update_tenant_names(self, entry, tenant_id_key):
        tenant_id = entry[tenant_id_key]
        tenant_name = self.identity_client.try_get_tenant_name_by_id(
            tenant_id, self.config.cloud.tenant)
        if self.table in IGNORED_TBL_LIST:
            tmp_tenant_id = self.identity_client.get_tenant_id_by_name(
                tenant_name)
        else:
            tmp_tenant_id = tenant_id
        if tmp_tenant_id == tenant_id:
            entry[tenant_id_key] = tenant_name
            return True
        else:
            LOG.debug('Ignored missed tenant %s', tenant_id)
            return False

    def _filter_volumes_list(self, volumes):
        filtering_enabled = self.cloud.position == 'src'

        if filtering_enabled:
            flts = self._get_volume_filter().get_filters()
            for f in flts:
                volumes = [v for v in volumes if f(v)]

            if flts:
                LOG.info("Filtered volumes: %s",
                         ", ".join((v['display_name'] for v in volumes)))
        return volumes

    def _filter_quotas_list(self, table_name, quotas):
        filtering_enabled = self.cloud.position == 'src'

        if filtering_enabled:
            fltr = self._get_volume_filter().get_tenant_filter()
            quotas = [q for q in quotas if fltr(q)]
            if fltr:
                LOG.info("Filtered %s: %s", table_name,
                         ", ".join((str(v) for v in quotas)))
        return quotas

    def _filter(self, table, result):
        if table == 'volumes':
            result = self._filter_volumes_list(result)
        if table in QUOTA_TABLES:
            result = self._filter_quotas_list(table, result)
        return result

    def list_of_dicts_for_table(self, table):
        """ Performs SQL query and returns rows as dict """
        # ignore deleted and errored volumes
        sql = ("SELECT * from {table}").format(table=table)
        query = self.mysql_connector.execute(sql)
        column_names = query.keys()
        result = [dict(zip(column_names, row)) for row in query]
        self.table = table
        # check if result has "deleted" column
        if DELETED in column_names:
            result = [a for a in result if a.get(DELETED) == 0]

        result = self._filter(table, result)

        if PROJECT_ID in column_names:
            result = [e for e in result
                      if self._check_update_tenant_names(e, PROJECT_ID)]
        if TENANT_ID in column_names:
            result = [e for e in result
                      if self._check_update_tenant_names(e, TENANT_ID)]
        if STATUS in column_names:
            result = [e for e in result if 'error' not in e[STATUS]]
        if USER_ID in column_names:
            for entry in result:
                entry[USER_ID] = self.identity_client.try_get_username_by_id(
                    entry[USER_ID], default=self.config.cloud.user)
        return result

    def read_db_info(self, **_):
        """ Returns serialized data from database """

        return jsondate.dumps(
            {i: self.list_of_dicts_for_table(i) for i in self.list_of_tables})

    def get_volume_host(self):
        # cached property
        if self.hosts is None:
            self.hosts = [i.host for i in self.cinder_client.services.list(
                binary=CINDER_VOLUME) if i.state == 'up']
        # return host by "round-robin" rule
        if self.host_counter:
            self.host_counter = 0
        self.host_counter += 1
        # counter modulo length of hosts will give
        # round robin results on each call
        if not self.hosts:
            raise RuntimeError("cannot find cinder volume service in cloud")
        return self.hosts[self.host_counter % len(self.hosts)]

    def deploy_data_to_table(self, table_name, table_list_of_dicts):
        """ Inserts data to database with single query """
        if not table_list_of_dicts:
            # if we don't have data to be added - exit
            return

        def get_key_and_auto_increment(cursor, table):
            """ get name of column that is primary_key, get auto_increment """
            cursor.execute(
                "show index from {table} where Key_name = 'PRIMARY'".format(
                    table=table))
            primary_key = cursor.fetchone().get("Column_name")
            cursor.execute(
                "select auto_increment from information_schema.tables"
                " where table_name = '{table}'".format(table=table))
            auto_increment = cursor.fetchone().get("auto_increment")
            return primary_key, auto_increment

        def filter_data(existing_data, data_to_be_added, primary_key,
                        auto_increment):
            """ handle duplicates in database """
            existing_hash = {i.get(primary_key): i for i in existing_data}
            unique_entries, duplicated_pk = [], []
            for candidate in data_to_be_added:
                key = candidate[primary_key]
                if key in existing_hash:
                    # compare intersection of 2 dicts
                    ex_hash = existing_hash[key]
                    x_ion = list(set(ex_hash.keys()) & set(candidate.keys()))
                    if ({i: candidate[i] for i in candidate if i in x_ion} ==
                            {i: ex_hash[i] for i in ex_hash if i in x_ion}):
                        # if dicts are comlpletely same - drop that dict
                        LOG.debug("duplicate in table %s for pk %s",
                                  table_name, key)
                    elif auto_increment:
                        # add entry to database without primary_key
                        # primary key will be generated automaticaly
                        duplicated_pk.append(
                            {i: candidate[i] for i in candidate
                             if i != primary_key})
                else:
                    unique_entries.append(candidate)
            return unique_entries, duplicated_pk

        def add_to_database(cursor, table, entries):
            """ insert dict to database """
            if not entries:
                return
            keys = entries[0].keys()
            query = "INSERT INTO {table} ({keys}) VALUES ({values})".format(
                    keys=",".join(keys),
                    table=table,
                    values=",".join(["%s" for _ in keys]))

            LOG.debug(query)
            cursor.executemany(query, [i.values() for i in entries])

        # create raw connection to db driver to get the most awesome features
        self.fix_entries(table_list_of_dicts)
        sql_engine = self.mysql_connector.get_engine()
        connection = sql_engine.raw_connection()
        cursor = connection.cursor(dictionary=True)
        primary_key, auto_increment = get_key_and_auto_increment(
            cursor, table_name)
        data_in_database = self.list_of_dicts_for_table(table_name)
        unique_entries, duplicated_pk = filter_data(data_in_database,
                                                    table_list_of_dicts,
                                                    primary_key,
                                                    auto_increment)
        add_to_database(cursor, table_name, unique_entries)
        add_to_database(cursor, table_name, duplicated_pk)
        cursor.close()
        connection.commit()
        connection.close()

    def fix_entries(self, table_list_of_dicts):
        """ Fix entries for Cinder Database.

        This method corrects entries to be injected to the database because we
        change SRC tenant-ids for tenant-names to get correct DST tenant-ids by
        names.

        :param table_list_of_dicts: list with database entries
        :param table_name: name of the database table
        :rtype: None
        """

        for entry in table_list_of_dicts:
            if PROJECT_ID in entry:
                entry[PROJECT_ID] = (
                    self.identity_client.get_tenant_by_name(
                        entry[PROJECT_ID]).id)
            if TENANT_ID in entry:
                entry[TENANT_ID] = (
                    self.identity_client.get_tenant_by_name(
                        entry[TENANT_ID]).id)
            if USER_ID in entry:
                user = self.identity_client.try_get_user_by_name(
                    username=entry[USER_ID],
                    default=self.config.cloud.user)
                entry[USER_ID] = user.id

    def deploy(self, data):
        """ Reads serialized data and writes it to database """
        for table_name, table_data in jsondate.loads(data).items():
            self.deploy_data_to_table(table_name, table_data)
