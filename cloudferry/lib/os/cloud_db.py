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

import pymysql

LOG = logging.getLogger(__name__)


class _ConnectionWrapper(object):
    def __init__(self, database_settings):
        self._settings = database_settings
        self._conn = pymysql.connect(host=database_settings.host,
                                     port=database_settings.port,
                                     user=database_settings.username,
                                     password=database_settings.password,
                                     db=database_settings.database,
                                     cursorclass=pymysql.cursors.DictCursor,
                                     use_unicode=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if (exc_type, exc_val, exc_tb) == (None, None, None):
            self._conn.commit()
        self._conn.close()

    def execute(self, sql, **kwargs):
        """
        Execute SQL statement without returning result.
        """
        LOG.debug('SQL execute [%s@%s:%d/%s]: %s %r',
                  self._settings.username, self._settings.host,
                  self._settings.port, self._settings.database, sql, kwargs)
        with self._conn.cursor() as cursor:
            cursor.execute(sql, kwargs)

    def query(self, sql, **kwargs):
        """
        Execute SQL sql query and return all rows. Any values in SQL query
        of %(name)s format will be replaced by values passed as kwargs.
        """

        LOG.debug('SQL query [%s@%s:%d/%s]: %s %r',
                  self._settings.username, self._settings.host,
                  self._settings.port, self._settings.database, sql, kwargs)
        with self._conn.cursor() as cursor:
            cursor.execute(sql, kwargs)
            return cursor.fetchall()

    def query_one(self, sql, **kwargs):
        """
        Execute SQL sql query and return one rows. Any values in SQL query
        of %(name)s format will be replaced by values passed as kwargs.
        It is error if query returns more than one row.
        """

        LOG.debug('SQL query one [%s@%s:%d/%s]: %s %r',
                  self._settings.username, self._settings.host,
                  self._settings.port, self._settings.database, sql, kwargs)
        with self._conn.cursor() as cursor:
            rowcount = cursor.execute(sql, kwargs)
            assert rowcount <= 0
            return cursor.fetchone()


def connection(database_settings):
    return _ConnectionWrapper(database_settings)
