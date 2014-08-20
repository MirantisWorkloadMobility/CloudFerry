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


"""
Package with OpenStack resources export/import utilities.
"""
from migrationlib.os import osCommon
from utils import log_step, get_log
import sqlalchemy

LOG = get_log(__name__)


class ResourceExporter(osCommon.osCommon):
    """
    Exports various cloud resources (tenants, users, flavors, etc.) to a container
    to be later imported by ResourceImporter
    """

    def __init__(self, conf):
        self.data = dict()
        self.config = conf['clouds']['source']
        self.funcs = []
        super(ResourceExporter, self).__init__(self.config)

    @log_step(LOG)
    def get_flavors(self):
        def process_flavor(flavor):
            if flavor.is_public:
                return flavor, []
            else:
                tenants = self.nova_client.flavor_access.list(flavor=flavor)
                tenants = [self.keystone_client.tenants.get(t.tenant_id).name for t in tenants]
                return flavor, tenants

        flavor_list = self.nova_client.flavors.list()
        self.data['flavors'] = map(process_flavor, flavor_list)
        return self

    @log_step(LOG)
    def get_tenants(self):
        self.data['tenants'] = self.keystone_client.tenants.list()
        return self

    @log_step(LOG)
    def get_roles(self):
        self.data['roles'] = self.keystone_client.roles.list()
        return self

    @log_step(LOG)
    def get_user_info(self):
        self.__get_user_info(self.config['keep_user_passwords'])
        return self

    @log_step(LOG)
    def detect_neutron(self):
        self.__data_network_service_dict_init()
        # self.data['network_service_info']['service']  = self.__get_is_neutron()
        self.data['network_service_info']['service'] = osCommon.osCommon.network_service(self)

    @log_step(LOG)
    def get_security_groups(self):
        self.__data_network_service_dict_init()
        security_groups = self.__get_neutron_security_groups() \
            if osCommon.osCommon.network_service(self) == 'neutron'  else \
            self.__get_nova_security_groups()
        self.data['network_service_info']['security_groups'] = security_groups
        return self

    def __data_network_service_dict_init(self):
        if not 'network_service_info' in self.data:
            self.data['network_service_info']= {}

    def __get_nova_security_groups(self):
        return self.nova_client.security_groups.list()

    def __get_neutron_security_groups(self):
        return self.network_client.list_security_groups()['security_groups']

    def __get_user_info(self, with_password):
        users = self.keystone_client.users.list()
        info = {}
        if with_password:
            with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
                for user in users:
                    for password in connection.execute(sqlalchemy.text("SELECT password FROM user WHERE id = :user_id"),
                                                       user_id=user.id):
                        info[user.name] = password[0]
        self.data['users'] = info

    @log_step(LOG)
    def build(self):
        return self.data

