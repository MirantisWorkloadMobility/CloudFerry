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


class TaskBuildResource(Task):

    def run(self, res_exporter=None, **kwargs):
        resources = res_exporter.build()
        return {
            'resources': resources
        }