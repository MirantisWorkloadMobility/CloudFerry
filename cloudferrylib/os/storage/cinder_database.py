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
from cloudferrylib.base import storage
from cloudferrylib.utils import utils as utl
from cloudferrylib.utils import mysql_connector

CINDER_VOLUME = "cinder-volume"
LOG = utl.get_log(__name__)
PROJECT_ID = 'project_id'
STATUS = 'status'
TENANT_ID = 'tenant_id'
USER_ID = 'user_id'
DELETED = 'deleted'
HOST = 'host'


class CinderStorage(storage.Storage):

    """Migration strategy used with NFS backend

    coppies data directly from database to database, avoiding creation of
    new volumes

    to use this strategy - specify cinder_migration_strategy in config as
    'cloudferrylib.os.storage.cinder_database.CinderStorage'

    """

    def __init__(self, config, cloud):
        self.config = config
        self.cloud = cloud
        self.identity_client = cloud.resources['identity']
        self.cinder_client = self.proxy(self.get_client(config), config)
        if not hasattr(cloud.config, cloud.position + '_storage'):
            LOG.debug('running on default mysql settings')
            self.connector = mysql_connector.MysqlConnector(
                self.config.mysql, 'cinder')
        else:
            LOG.debug('running on custom mysql settings')
            settings = getattr(cloud.config, cloud.position + '_storage')
            self.connector = mysql_connector.MysqlConnector(
                settings, settings.database_name)

        # FIXME This class holds logic for all these tables. These must be
        # split into separate classes
        self.list_of_tables = [
            'volumes',
            'quotas',
            'quota_classes',
            'quota_usages',
            'reservations',
            'snapshots',
            'snapshot_metadata',
            'volume_types']
        super(CinderStorage, self).__init__(config)

    def get_client(self, params=None):

        params = self.config if not params else params
        return cinder_client.Client(
            params.cloud.user,
            params.cloud.password,
            params.cloud.tenant,
            params.cloud.auth_url)

    def _update_tenant_names(self, result, tenant_id_key):
        for entry in result:
            tenant_name = self.identity_client.try_get_tenant_name_by_id(
                entry[tenant_id_key], self.config.cloud.tenant)
            entry[tenant_id_key] = tenant_name

    def list_of_dicts_for_table(self, table):
        """ Performs SQL query and returns rows as dict """
        # ignore deleted and errored volumes
        sql = ("SELECT * from {table}").format(table=table)
        query = self.connector.execute(sql)
        column_names = query.keys()
        result = [dict(zip(column_names, row)) for row in query]
        # check if result has "deleted" column
        if DELETED in column_names:
            result = filter(lambda a: a.get(DELETED) == 0, result)
        if PROJECT_ID in column_names:
            self._update_tenant_names(result, PROJECT_ID)
        if TENANT_ID in column_names:
            self._update_tenant_names(result, TENANT_ID)
        if STATUS in column_names:
            result = filter(lambda e: 'error' not in e[STATUS], result)
        if USER_ID in column_names:
            for entry in result:
                entry[USER_ID] = self.identity_client.try_get_username_by_id(
                    entry[USER_ID], default=self.config.cloud.user)
        return result

    def read_info(self):
        """ Returns serialized data from database """
        return jsondate.dumps(
            {i: self.list_of_dicts_for_table(i) for i in self.list_of_tables})

    def get_volume_host(self):
        # cached property
        if not hasattr(self, 'hosts'):
            self.hosts = [i.host for i in self.cinder_client.services.list(
                binary=CINDER_VOLUME)]
        # return host by "round-robin" rule
        if not hasattr(self, "host_counter"):
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

        def filter_data(existing_data, data_to_be_added, primary_key, auto_increment):
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
                        LOG.debug(
                            "duplicate in table {table} for pk {pk}".format(
                                pk=key,
                                table=table_name))
                    elif auto_increment:
                        # add entry to database without primary_key
                        # primary key will be generated automaticaly
                        duplicated_pk.append(
                            {i: candidate[i] for i in candidate if i != primary_key})
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
                    table=table_name,
                    values=",".join(["%s" for i in keys]))
            cursor.executemany(query, [i.values() for i in entries])

        def fix_entries(table_list_of_dicts):
            # this function corrects entries to be injected to db
            # because we change src tenant-ids for tenant-names
            # to get correct dst tenant-ids by name
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
                    entry[USER_ID] = (
                        self.identity_client.keystone_client.users.find(
                            username=entry[USER_ID]).id)
                if HOST in entry:
                    entry[HOST] = self.get_volume_host()

        # create raw connection to db driver to get the most awesome features
        fix_entries(table_list_of_dicts)
        sql_engine = self.connector.get_engine()
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

    def deploy(self, data):
        """ Reads serialized data and writes it to database """
        for table_name, table_data in jsondate.loads(data).items():
            self.deploy_data_to_table(table_name, table_data)
