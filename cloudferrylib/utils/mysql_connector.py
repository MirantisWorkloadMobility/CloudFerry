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


import sqlalchemy


class MysqlConnector():
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.connection_url = self.compose_connection_url()

    def compose_connection_url(self):
        return '{}://{}:{}@{}:{}/{}'.format(self.config['connection'],
                                            self.config['user'],
                                            self.config['password'],
                                            self.config['host'],
                                            self.config['port'],
                                            self.db)

    def get_engine(self):
        return sqlalchemy.create_engine(self.connection_url)

    def execute(self, command, **kwargs):
        with sqlalchemy.create_engine(
                self.connection_url).begin() as connection:
            return connection.execute(sqlalchemy.text(command), **kwargs)
