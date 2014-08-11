from scheduler.SuperTask import SuperTask
from SuperTaskImportInstance import SuperTaskImportInstance
from SuperTaskExportInstance import SuperTaskExportInstance

__author__ = 'mirrorcoder'


class SuperTaskMigrateInstances(SuperTask):

    def search_instances_by_search_opts(self, config, exporter):
        for instance_search_opts in config['instances']:
            for instance in exporter.find_instances(instance_search_opts):
                yield instance

    def run(self, config=None, inst_exporter=None, **kwargs):
        supertasks_migrate = []
        for instance in self.search_instances_by_search_opts(config, inst_exporter):
            supertasks_migrate.append(SuperTaskExportInstance(instance=instance))
            supertasks_migrate.append(SuperTaskImportInstance())
        return supertasks_migrate