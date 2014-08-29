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


class MainInfoResource(osCommon.osCommon):

    def __init__(self, conf):
        self.source_info = dict()
        self.config = conf
        super(MainInfoResource, self).__init__(self.config)

    def info_services_list(self):
        self.source_info['services']= self.keystone_client.services.list()
        return self.source_info['services']

    def info_tenants_list(self):
        self.source_info['tenants']= self.keystone_client.tenants.list()
        print self.source_info['tenants']
        return self.source_info['tenants']

    def info_users_list(self):
        self.source_info['users']= self.keystone_client.users.list()
        return self.source_info['users']

    def build_info(self):
        write_info(render_info(self.source_info))
        print render_info(self.source_info)
        return render_info(self.source_info)

class InfoResource(MainInfoResource):

    def __init__(self, tenant, conf):
        self.config=conf
        conf['tenant'] = tenant.name
        super(InfoResource, self).__init__(self.config)
        self.source_info['tenant_info'] = dict()
        self.source_info['tenant_info'][tenant.name] = dict()
        self.source_info = self.source_info['tenant_info'][tenant.name]


