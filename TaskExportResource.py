from Task import Task
from SuperTask import SuperTask
from utils import *
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

    def func(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_tenants()
        return {
            'resources': resources
        }


class TaskExportRolesResource(Task):

    def func(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_roles()
        return {
            'resources': resources
        }


class TaskFlavorsTenantsResource(Task):

    def func(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_flavors()
        return {
            'resources': resources
        }


class TaskUserInfoTenantsResource(Task):

    def func(self, res_exporter=None, **kwargs):
        resources = res_exporter.get_user_info()
        return {
            'resources': resources
        }


class TaskBuildResource(Task):

    def func(self, res_exporter=None, **kwargs):
        resources = res_exporter.build()
        return {
            'resources': resources
        }