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
from utils import get_log

__author__ = 'mirrorcoder'

LOG = get_log(__name__)


class SuperTaskExportResource(SuperTask):

    def run(self, res_exporter=None, **kwargs):
        return [TaskExportTenantsResource(),
                TaskExportRolesResource(),
                TaskFlavorsTenantsResource(),
                TaskUserInfoTenantsResource(),
                TaskNetworkServiceInfoResource(),
                TaskSecurityGroupsResource(),
                TaskBuildResource()]


class TaskExportTenantsResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_tenants()
        return {
            'resources': resources
        }


class TaskExportRolesResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_roles()
        return {
            'resources': resources
        }


class TaskFlavorsTenantsResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_flavors()
        return {
            'resources': resources
        }


class TaskUserInfoTenantsResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_user_info()
        return {
            'resources': resources
        }


class TaskNetworkServiceInfoResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.detect_neutron()
        return {
            'resources': resources
        }


class TaskSecurityGroupsResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_security_groups()
        return {
            'resources': resources
        }


class TaskBuildResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.build()
        return {
            'resources': resources
        }