import yaml
from fabric.api import task, env
from scheduler.Namespace import Namespace
from scheduler.Scheduler import Scheduler
from tasks.SuperTaskImportResource import SuperTaskImportResource
from tasks.TaskInitMigrate import TaskInitMigrate
from tasks.SuperTaskExportResource import SuperTaskExportResource
from tasks.SuperTaskMigrateInstances import SuperTaskMigrateInstances
from utils import log_step, get_log

env.forward_agent = True
env.user = 'root'

LOG = get_log(__name__)


@task
def migrate(name_config, name_instance=None):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    namespace = Namespace({'__name_config__': name_config,
                           'name_instance': name_instance})
    scheduler = Scheduler(namespace)
    scheduler.addTask(TaskInitMigrate())
    # scheduler.addTask(SuperTaskExportResource())
    # scheduler.addTask(SuperTaskImportResource())
    scheduler.addTask(SuperTaskMigrateInstances())
    print "RUN!!"
    scheduler.run()
    print scheduler.tasks_runned


@task
def clean_dest_cloud(name_config, delete_image=False):
    LOG.info("Init config migrate")
    # _, (_, _), (_, importer) = init_migrate(name_config)
    # importer.clean_cloud(delete_image)
