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
import sqlite3

import mock

from tests import test
from cloudferrylib.utils import local_db


class UnclosableConnection(sqlite3.Connection):
    def close(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if kwargs.get('i_mean_it'):
            super(UnclosableConnection, self).close()


class DatabaseMockingTestCase(test.TestCase):
    def setUp(self):
        super(DatabaseMockingTestCase, self).setUp()

        connection = sqlite3.connect(
            ':memory:', factory=UnclosableConnection,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.addCleanup(connection.close, i_mean_it=True)

        sqlite3_connect_patcher = mock.patch('sqlite3.connect')
        self.addCleanup(sqlite3_connect_patcher.stop)
        connect_mock = sqlite3_connect_patcher.start()
        connect_mock.return_value = connection

        local_db.execute_saved_statements(connection, force=True)


class LocalDbTestCase(DatabaseMockingTestCase):
    def setUp(self):
        super(LocalDbTestCase, self).setUp()
        with local_db.Transaction() as tx:
            tx.execute("""CREATE TABLE IF NOT EXISTS tests (
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (key)
                )""")

    def test_write_read_same_tx(self):
        with local_db.Transaction() as tx:
            tx.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('bar', row['value'])

    def test_write_read_different_tx(self):
        with local_db.Transaction() as tx:
            tx.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')
        with local_db.Transaction() as tx:
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('bar', row['value'])

    def test_write_write_read(self):
        with local_db.Transaction() as tx:
            tx.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')
        with local_db.Transaction() as tx:
            tx.execute('UPDATE tests SET value=:v WHERE key=:k',
                       k='foo', v='baz')
        with local_db.Transaction() as tx:
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('baz', row['value'])

    def test_write_write_rollback_read_first_value(self):
        with local_db.Transaction() as tx:
            tx.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')
        try:
            with local_db.Transaction() as tx:
                tx.execute('UPDATE tests SET value=:v WHERE key=:k',
                           k='foo', v='baz')
                raise RuntimeError()
        except RuntimeError:
            pass
        with local_db.Transaction() as tx:
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('bar', row['value'])

    def test_nested_tx(self):
        with local_db.Transaction() as tx1:
            tx1.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')
            with local_db.Transaction() as tx2:
                tx2.execute('UPDATE tests SET value=:v WHERE key=:k',
                            k='foo', v='baz')
        with local_db.Transaction() as tx:
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('baz', row['value'])

    def test_nested_tx_rollback_inner(self):
        with local_db.Transaction() as tx1:
            tx1.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')
            try:
                with local_db.Transaction() as tx2:
                    tx2.execute('UPDATE tests SET value=:v WHERE key=:k',
                                k='foo', v='baz')
                    raise RuntimeError()
            except RuntimeError:
                pass
        with local_db.Transaction() as tx:
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('bar', row['value'])

    def test_nested_tx_rollback_outer(self):
        # Prepare state
        with local_db.Transaction() as tx:
            tx.execute('INSERT INTO tests VALUES (:k, :v)', k='foo', v='bar')

        # Run outer rollback from inner tx
        try:
            with local_db.Transaction() as tx1:
                tx1.execute('UPDATE tests SET value=:v WHERE key=:k',
                            k='foo', v='baz')
                with local_db.Transaction() as tx2:
                    tx2.execute('UPDATE tests SET value=:v WHERE key=:k',
                                k='foo', v='qux')
                    raise RuntimeError()
        except RuntimeError:
            pass
        with local_db.Transaction() as tx:
            row = tx.query_one('SELECT value FROM tests WHERE key=:k', k='foo')
            self.assertEqual('bar', row['value'])
