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
import contextlib
import json
import logging
import os
import random
import sqlite3
import threading
import time

LOG = logging.getLogger(__name__)
SQLITE3_DATABASE_FILE = os.environ.get('CF_LOCAL_DB', 'migration_data.db')
_execute_once_statements = []
_executed_statements = set()
_execute_once_mutex = threading.Lock()


class Transaction(object):
    _tls = threading.local()
    _tls.top_level = None
    _tls.depth = 0

    def __init__(self):
        self._conn = None
        self._cursor = None
        self._name = self._generate_name()
        self._depth = None

    def __enter__(self):
        self._depth = self._tls.depth
        self._tls.depth += 1
        self._initialize()
        LOG.debug('Transaction started [depth=%d,name=%s]',
                  self._depth, self._name)
        self._do_begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        exc_info = (exc_type, exc_val, exc_tb)
        try:
            if exc_info == (None, None, None):
                self._do_commit()
            else:
                self._do_rollback()
                LOG.debug('Transaction rollback because of exception',
                          exc_info=(exc_type, exc_val, exc_tb))
        finally:
            self._cursor.close()
            if self._depth == 0:
                self._conn.close()
            self._tls.depth -= 1
            LOG.debug('Transaction completed [depth=%d,name=%s]',
                      self._depth, self._name)

    def _initialize(self):
        # pylint: disable=protected-access
        if self._depth == 0:
            self._tls.top_level = self
            self._conn = sqlite3.connect(
                SQLITE3_DATABASE_FILE,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            self._conn.row_factory = sqlite3.Row
            self._conn.isolation_level = None
            execute_saved_statements(self._conn)
        else:
            self._conn = self._tls.top_level._conn
        self._cursor = self._conn.cursor()

    def _do_begin(self):
        if self._depth == 0:
            self.execute('BEGIN EXCLUSIVE')
        else:
            self.execute('SAVEPOINT tx_{}'.format(self._name))

    def _do_commit(self):
        if self._depth == 0:
            self.execute('COMMIT')
        else:
            self.execute('RELEASE tx_{}'.format(self._name))

    def _do_rollback(self):
        if self._depth == 0:
            self.execute('ROLLBACK')
        else:
            self.execute('ROLLBACK TO SAVEPOINT tx_{}'.format(self._name))

    @staticmethod
    def _generate_name():
        rnd = random.Random(time.time())
        return '{:032x}'.format(rnd.getrandbits(8 * 16))

    def execute(self, sql, **kwargs):
        """
        Execute SQL statement without returning result.
        """
        LOG.debug('SQL execute [%s]: %s %r', self._name, sql, kwargs)
        self._cursor.execute(sql, kwargs)

    def query(self, sql, **kwargs):
        """
        Execute SQL sql query and return all rows. Any values in SQL query
        of :name format will be replaced by values passed as kwargs.
        """
        LOG.debug('SQL query [%s]: %s %r', self._name, sql, kwargs)
        self._cursor.execute(sql, kwargs)
        return self._cursor.fetchall()

    def query_one(self, sql, **kwargs):
        """
        Execute SQL sql query and return one rows. Any values in SQL query
        of :name format will be replaced by values passed as kwargs.
        It is error if query returns more than one row.
        """
        LOG.debug('SQL query one [%s]: %s %r', self._name, sql, kwargs)
        self._cursor.execute(sql, kwargs)
        assert self._cursor.rowcount <= 1
        return self._cursor.fetchone()


class Json(object):
    """
    Objects of this class become JSON when converted to string or unicode
    """

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        try:
            return json.dumps(self.data, indent=2, sort_keys=True)
        except TypeError:
            return '<Unserializable JSON>'

    @classmethod
    def adapt(cls, obj):
        assert isinstance(obj, cls)
        return json.dumps(obj.data, sort_keys=True)

    @classmethod
    def convert(cls, value):
        return Json(json.loads(value))


def execute_once(sql, **kwargs):
    """
    This function register SQL statement that will be executed only once during
    program lifetime. The idea behind this function is to execute table
    creation SQL only once.
    :param sql: SQL statement string
    :param kwargs: SQL statement arguments
    """
    with _execute_once_mutex:
        _execute_once_statements.append((sql.strip(), kwargs))


def execute_saved_statements(conn, force=False):
    """
    Execute statements registered with execute_once.
    :param conn: SQLite3 connection
    :param force: if force is set to True, then all previously executed SQL
                  statements will be ignored and will executed again.
                  This parameter is introduced for testing.
    :return:
    """
    with _execute_once_mutex, contextlib.closing(conn.cursor()) as cursor:
        for sql, kwargs in _execute_once_statements:
            key = (sql, tuple(sorted(kwargs.items())))
            if key in _executed_statements or force:
                LOG.debug('SQL execute once: %s %r', sql, kwargs)
                cursor.execute(sql, kwargs)
                _executed_statements.add(key)


sqlite3.register_adapter(Json, Json.adapt)
sqlite3.register_converter('json', Json.convert)
