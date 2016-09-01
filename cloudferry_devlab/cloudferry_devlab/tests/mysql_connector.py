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


import pymysql


class MysqlConnector(object):
    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.connection_dict = self.compose_connection_dict()

    def compose_connection_dict(self):
        data = {
            'host': self.config['db_host'],
            'port': int(self.config['db_port']),
            'user': self.config['db_user'],
            'password': self.config['db_password'],
            'db': self.db,
            'cursorclass': pymysql.cursors.DictCursor
        }
        return data

    def execute(self, command):
        connection = pymysql.connect(**self.connection_dict)
        try:
            with connection.cursor() as cursor:
                cursor.execute(command)
                connection.commit()
                return cursor
        finally:
            connection.close()
