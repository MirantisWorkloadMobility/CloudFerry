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