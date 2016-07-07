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
import time

import pymysql
import sqlalchemy

from cloudferry.lib.utils import remote_runner
from cloudferry.lib.utils import local

ALL_DATABASES = "--all-databases"

MySQLError = pymysql.MySQLError


def get_db_host(cloud_config):
    """Returns DB host based on configuration.

    Useful when MySQL is deployed on multiple nodes, when multiple MySQL nodes
    are hidden behind a VIP. In this scenario providing VIP in
    `config.dst_mysql.db_host` will break mysqldump which requires to be run
    locally on particular DB host.

    :returns: `config.migrate.mysqldump_host` if not `None`, or
    `config.dst_mysql.db_host` otherwise
    """

    return cloud_config.mysqldump.mysqldump_host or cloud_config.mysql.db_host


def dump_db(cloud, database=ALL_DATABASES):
    cmd = ["mysqldump {database}",
           "--user={user}"]
    if cloud.cloud_config.mysql.db_password:
        cmd.append("--password={password}")

    db_host = get_db_host(cloud.cloud_config)
    if cloud.cloud_config.mysqldump.run_mysqldump_locally:
        cmd.append("--port={port}")
        cmd.append("--host={host}")
        run = local.run
    else:
        rr = remote_runner.RemoteRunner(
            db_host, cloud.cloud_config.cloud.ssh_user,
            password=cloud.cloud_config.cloud.ssh_sudo_password,
            mute_stdout=True)
        run = rr.run

    dump = run(' '.join(cmd).format(
        database=database,
        user=cloud.cloud_config.mysql.db_user,
        password=cloud.cloud_config.mysql.db_password,
        port=cloud.cloud_config.mysql.db_port,
        host=cloud.cloud_config.mysql.db_host))

    filename = cloud.cloud_config.mysqldump.db_dump_filename
    with open(filename.format(database=('all_databases'
                                        if database == ALL_DATABASES
                                        else database),
                              time=time.time(),
                              position=cloud.position), 'w') as f:
        f.write(dump)


class MysqlConnector(object):
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.connection_url = self.compose_connection_url()
        self._connection = None

    def compose_connection_url(self):
        return '{}://{}:{}@{}:{}/{}'.format(self.config['db_connection'],
                                            self.config['db_user'],
                                            self.config['db_password'],
                                            self.config['db_host'],
                                            self.config['db_port'],
                                            self.db)

    def get_engine(self):
        return sqlalchemy.create_engine(self.connection_url)

    def execute(self, command, **kwargs):
        with self.transaction() as connection:
            return connection.execute(sqlalchemy.text(command), **kwargs)

    def batch_execute(self, commands, **kwargs):
        with self.transaction() as connection:
            for command in commands:
                connection.execute(sqlalchemy.text(command), **kwargs)

    @contextlib.contextmanager
    def transaction(self):
        if self._connection:
            yield self._connection
        else:
            with self.get_engine().begin() as conn:
                self._connection = conn
                try:
                    yield conn
                finally:
                    self._connection = None
