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