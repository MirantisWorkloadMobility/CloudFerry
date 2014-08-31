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

from scheduler.SuperTask import SuperTask
from scheduler.Task import Task
from migrationlib.os.exporter import osInfo
from utils import log_step, get_log, render_info, write_info

LOG = get_log(__name__)

class SuperTaskInfoSource(SuperTask):
    def run(self, main_tenant=None, **kwargs):
        return [TaskInfoTenantsSource(),
                TaskInfoServicesSource(),
                TaskInfoUsersSource(),
                TaskInfoBuild()]

class TaskInfoServicesSource(Task):
    def run(self, main_tenant=None, **kwargs):
        source_info = main_tenant.info_services_list()
        return {
            'source_info': source_info
        }

class TaskInfoTenantsSource(Task):
    def run(self, main_tenant=None, **kwargs):
        tenants_list = main_tenant.info_tenants_list()
        return {
            'tenants_list': tenants_list
        }

class TaskInfoUsersSource(Task):
    def run(self, main_tenant=None, **kwargs):
        users_list = main_tenant.info_users_list()
        return {
            'users_list': users_list
        }


class TaskInfoBuild(Task):
    def run(self, **kwargs):
        rendered_info = osInfo.MainInfoResource.build_info(osInfo.MainInfoResource.source_info)
        return {
            'rendered_info': rendered_info
        }
