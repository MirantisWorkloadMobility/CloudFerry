from scheduler.SuperTask import SuperTask
from SuperTaskImportInstance import SuperTaskImportInstance
from SuperTaskExportInstance import SuperTaskExportInstance
from tasks.TransactionsListenerOs import TransactionsListenerOs
from scheduler.transaction.TaskTransaction import TaskTransactionBegin, TaskTransactionEnd
from tasks.TaskCreateSnapshotOs import TaskCreateSnapshotOs
__author__ = 'mirrorcoder'


class SuperTaskMigrateInstances(SuperTask):

    def search_instances_by_search_opts(self, config, exporter):
        for instance_search_opts in config['instances']:
            for instance in exporter.find_instances(instance_search_opts):
                yield instance

    def run(self, config=None, inst_exporter=None, **kwargs):
        supertasks_migrate = []
        supertasks_migrate.append(TaskCreateSnapshotOs())
        for instance in self.search_instances_by_search_opts(config, inst_exporter):
            supertasks_migrate.append(TaskTransactionBegin(transaction_listener=TransactionsListenerOs(instance)))
            supertasks_migrate.append(SuperTaskExportInstance(instance=instance))
            supertasks_migrate.append(SuperTaskImportInstance())
            supertasks_migrate.append(TaskCreateSnapshotOs())
            supertasks_migrate.append(TaskTransactionEnd())
        return supertasks_migrate