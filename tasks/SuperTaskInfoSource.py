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
from utils import get_log

LOG = get_log(__name__)
SERVICE_TENANTS = ['service', 'services','invisible_to_admin']


class SuperTaskInfoSource(SuperTask):
    def run(self, main_tenant=None, **kwargs):
        return [TaskInfoTenantsSource(),
                TaskInfoServicesSource(),
                TaskInfoHypervisorsSource(),
                TaskInfoUsersSource(),
                TaskInfoImagesSource(),
                TaskInfoVolumesSource(),
                TaskInfoRolesSource(),
                TaskInfoServersSource(),
                TaskInfoBuild()]

class TaskInfoServicesSource(Task):
    def run(self, main_tenant=None, **kwargs):
        services_info = main_tenant.info_services_list()
        return {
            'services_info': services_info
        }

class TaskInfoHypervisorsSource(Task):
    def run(self, main_tenant=None, **kwargs):
        hypervisors_info = main_tenant.info_hypervisors_list()
        return {
            'hypervisors_info': hypervisors_info
        }

class TaskInfoTenantsSource(Task):
    def run(self, main_tenant=None, **kwargs):
        tenants_list = main_tenant.info_tenants_list()
        return {
            'tenants_list': tenants_list
        }

class TaskInfoUsersSource(Task):
    def run(self, tenants_info= None, tenants_list = None, **kwargs):
        info_users = list()
        for tenant in tenants_list:
            if not tenant.name in SERVICE_TENANTS:
                users_list = tenants_info[tenant.name].info_users_list()
                info_users.append(users_list)
        return {
            'info_users': info_users
        }

class TaskInfoImagesSource(Task):
    def run(self, tenants_info= None, tenants_list = None, **kwargs):
        info_images = list()
        for tenant in tenants_list:
            if not tenant.name in SERVICE_TENANTS:
                images_list = tenants_info[tenant.name].info_images_list()
                info_images.append(images_list)
        return {
            'info_images': info_images
        }

class TaskInfoVolumesSource(Task):
    def run(self, tenants_info= None, tenants_list = None, **kwargs):
        info_volumes = list()
        for tenant in tenants_list:
            if not tenant.name in SERVICE_TENANTS:
                volumes_list = tenants_info[tenant.name].info_volumes_list()
                info_volumes.append(volumes_list)
        return {
            'info_volumes': info_volumes
        }

class TaskInfoRolesSource(Task):
    def run(self, tenants_info= None, tenants_list = None, **kwargs):
        info_roles= list()
        for tenant in tenants_list:
            if not tenant.name in SERVICE_TENANTS:
                roles_list = tenants_info[tenant.name].info_roles_list()
                info_roles.append(roles_list)
        return {
            'info_roles': info_roles
        }

class TaskInfoServersSource(Task):
    def run(self, tenants_info= None, tenants_list = None, **kwargs):
        info_servers= list()
        for tenant in tenants_list:
            if not tenant.name in SERVICE_TENANTS:
                servers_list = tenants_info[tenant.name].info_servers_list()
                info_servers.append(servers_list)
        return {
            'info_roles': info_servers
        }

class TaskInfoBuild(Task):
    def run(self, **kwargs):
        rendered_info = osInfo.MainInfoResource.build_info(osInfo.MainInfoResource.source_info)
        return {
            'rendered_info': rendered_info
        }