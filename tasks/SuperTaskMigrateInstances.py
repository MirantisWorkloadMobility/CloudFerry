from scheduler.SuperTask import SuperTask
from SuperTaskImportInstance import SuperTaskImportInstance
from SuperTaskExportInstance import SuperTaskExportInstance
from tasks.TransactionsListenerOs import TransactionsListenerOs
from scheduler.transaction.TaskTransaction import TaskTransactionBegin, TaskTransactionEnd
from tasks.TaskCreateSnapshotOs import TaskCreateSnapshotOs
from migrationlib.os.utils.rollback.RollbackOpenStack import RollbackOpenStack
from tasks.TaskRestoreSourceCloud import TaskRestoreSourceCloud
__author__ = 'mirrorcoder'


class SuperTaskMigrateInstances(SuperTask):

    def search_instances_by_search_opts(self, config, exporter):
        for instance_search_opts in config['instances']:
            for instance in exporter.find_instances(instance_search_opts):
                yield instance

    def run(self, config=None, inst_exporter=None, inst_importer=None, __rollback_status__=None, **kwargs):
        supertasks_migrate = []
        for instance in self.search_instances_by_search_opts(config, inst_exporter):
            supertasks_migrate.append(TaskCreateSnapshotOs())
            supertasks_migrate.append(TaskTransactionBegin(
                transaction_listener=TransactionsListenerOs(instance,
                                                            rollback=RollbackOpenStack(instance.id,
                                                                                       inst_exporter,
                                                                                       inst_importer))))
            supertasks_migrate.append(SuperTaskExportInstance(instance=instance))
            supertasks_migrate.append(SuperTaskImportInstance())
            supertasks_migrate.append(TaskCreateSnapshotOs())
            supertasks_migrate.append(TaskTransactionEnd())
            supertasks_migrate.append(TaskRestoreSourceCloud())
        return supertasks_migrate