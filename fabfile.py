import yaml
from fabric.api import task, env
from scheduler.Namespace import Namespace
from scheduler.Scheduler import Scheduler
from tasks.SuperTaskImportResource import SuperTaskImportResource
from tasks.TaskInitMigrate import TaskInitMigrate
from tasks.SuperTaskExportResource import SuperTaskExportResource
from tasks.TaskCreateSnapshotOs import TaskCreateSnapshotOs
from tasks.SuperTaskMigrateInstances import SuperTaskMigrateInstances
from utils import log_step, get_log
import os
import shutil
from migrationlib.os.utils.rollback.Rollback import *
env.forward_agent = True
env.user = 'root'

LOG = get_log(__name__)


@task
def migrate(name_config, name_instance=None, mode=RETRY):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    if mode == RESTART:
        if os.path.exists("transaction"):
            shutil.rmtree("transaction")
        if os.path.exists("snapshots"):
            shutil.rmtree("snapshots")
    if mode == ABORT:
        if os.path.exists("transaction"):
            shutil.rmtree("transaction")
        if os.path.exists("snapshots"):
            shutil.rmtree("snapshots")
    rollback_status = mode
    namespace = Namespace({'__name_config__': name_config,
                           'name_instance': name_instance,
                           '__rollback_status__': rollback_status})
    scheduler = Scheduler(namespace)

    scheduler.addTaskExclusion(TaskCreateSnapshotOs)
    scheduler.addTask(TaskInitMigrate())
    scheduler.addTask(SuperTaskExportResource())
    scheduler.addTask(SuperTaskImportResource())
    scheduler.addTask(SuperTaskMigrateInstances())
    print "RUN!!"
    scheduler.run()


@task
def clean_dest_cloud(name_config, delete_image=False):
    LOG.info("Init config migrate")
    # _, (_, _), (_, importer) = init_migrate(name_config)
    # importer.clean_cloud(delete_image)

if __name__ == '__main__':
    migrate('configs/config_iscsi_to_iscsi.yaml')
