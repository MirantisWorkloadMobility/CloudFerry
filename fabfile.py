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

from fabric.api import task, env
from scheduler.Namespace import Namespace
from scheduler.Scheduler import Scheduler
from tasks.SuperTaskImportResource import SuperTaskImportResource
from tasks.TaskInitMigrate import TaskInitMigrate
from tasks.SuperTaskExportResource import SuperTaskExportResource
from tasks.TaskCreateSnapshotOs import TaskCreateSnapshotOs
from tasks.SuperTaskMigrateInstances import SuperTaskMigrateInstances
from tasks.TaskSourceInfo import TaskSourceInfo
from tasks.SuperTaskInfoSource import SuperTaskInfoSource
from tasks.TaskRestoreSourceCloud import TaskRestoreSourceCloud
from tasks.TaskRestoreDestCloud import TaskRestoreDestCloud
from tasks.TaskInitDirectory import TaskInitDirectory
from tasks.TaskLoadSnapshotsForAbort import TaskLoadSnapshotsForAbort
from utils import log_step, get_log, load_json_from_file, get_snapshots_list_repository, PATH_TO_SNAPSHOTS
import os
import shutil
from migrationlib.os.utils.rollback.Rollback import *


env.forward_agent = True
env.user = 'root'

LOG = get_log(__name__)


@task
def migrate(name_config, name_instance=None, mode=DEFAULT):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    rollback_status = mode
    namespace = Namespace({'__name_config__': name_config,
                           'name_instance': name_instance,
                           '__rollback_status__': rollback_status if not (rollback_status == DEFAULT) else RESTART})
    scheduler = Scheduler(namespace)
    if rollback_status == DEFAULT:
        scheduler.addTask(TaskInitMigrate())
        scheduler.addTask(TaskInitDirectory())

    if (rollback_status == RETRY) or (rollback_status == SKIP):
        scheduler.addTask(TaskInitMigrate())

    if (rollback_status == RESTART) or (rollback_status == ABORT):
        if os.path.exists(PATH_TO_SNAPSHOTS):
            scheduler.addTask(TaskInitMigrate())
            scheduler.addTask(TaskLoadSnapshotsForAbort())
            scheduler.addTask(TaskCreateSnapshotOs())
            scheduler.addTask(TaskRestoreSourceCloud())
            scheduler.addTask(TaskRestoreDestCloud())
        elif rollback_status == RESTART:
            scheduler.addTask(TaskInitMigrate())
        scheduler.addTask(TaskInitDirectory())

    if rollback_status == ABORT:
        scheduler.run()
        return

    scheduler.addTaskExclusion(TaskCreateSnapshotOs)
    scheduler.addTask(SuperTaskExportResource())
    scheduler.addTask(SuperTaskImportResource())
    scheduler.addTask(SuperTaskMigrateInstances())
    scheduler.run()


@task
def clean_dest_cloud(name_config, delete_image=False):
    LOG.info("Init config migrate")
    # _, (_, _), (_, importer) = init_migrate(name_config)
    # importer.clean_cloud(delete_image)

@task
def get_info(name_config):
    LOG.info("Init getting information")
    namespace = Namespace({'name_config': name_config})
    scheduler = Scheduler(namespace)
    scheduler.addTask(TaskSourceInfo())
    scheduler.addTask(SuperTaskInfoSource())
    scheduler.run()

if __name__ == '__main__':
    migrate('configs/config_iscsi_to_iscsi.yaml', mode=DEFAULT)
