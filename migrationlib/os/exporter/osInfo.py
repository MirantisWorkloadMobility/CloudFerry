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
    source_info['tenants_info'] = dict()

    def __init__(self, config):
        self.config = config
        self.tenant_name = self.config['tenant']
        print "Passed to args class tenant_name", self.tenant_name
        MainInfoResource.source_info['tenants_info'][self.tenant_name] = dict()
        print "Create new tenant_info Unit = ", self.tenant_name
        super(MainInfoResource, self).__init__(self.config)

    def info_services_list(self):
        MainInfoResource.source_info['services'] = self.keystone_client.services.list()
        return self.keystone_client.services.list()

    def info_tenants_list(self):
        MainInfoResource.source_info['tenants'] = self.keystone_client.tenants.list()
        return self.keystone_client.tenants.list()

    def info_users_list(self):
        MainInfoResource.source_info['tenants_info'][self.tenant_name]['users'] = self.keystone_client.users.list()
        return self.keystone_client.users.list()

    def info_roles_list(self):
        MainInfoResource.source_info['roles'] = self.keystone_client.roles.list()
        return self.keystone_client.roles.list()

    def info_images_list(self):
        MainInfoResource.source_info['tenants_info'][self.tenant_name]['images'] = self.glance_client.images.list()
        return self.glance_client.images.list()

    @staticmethod
    def build_info(info):
        print info['tenants_info']
        write_info(render_info(info))
        return render_info(info)