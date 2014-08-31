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
Package with OpenStack info class.
"""

from migrationlib.os import osCommon
from utils import log_step, get_log, render_info, write_info
import yaml


class MainInfoResource(osCommon.osCommon):

    source_info = dict()

    def __init__(self, conf, tenant_name = None):
        self.config = conf
        if tenant_name:
            self.tenant_name = tenant_name
        else:
            self.tenant_name = 'admin'
        MainInfoResource.source_info[self.tenant_name] = dict()
        super(MainInfoResource, self).__init__(self.config)

    def info_services_list(self):
        MainInfoResource.source_info['services'] = self.keystone_client.services.list()
        return self.keystone_client.services.list()

    def info_tenants_list(self):
        MainInfoResource.source_info['tenants'] = [tenant.name for tenant in self.keystone_client.tenants.list()]
        return self.keystone_client.tenants.list()

    def info_users_list(self):
        MainInfoResource.source_info[self.tenant_name]['users'] = self.keystone_client.users.list()
        return self.keystone_client.users.list()


    @staticmethod
    def build_info(info):
        write_info(render_info(info)
        return render_info(info)


