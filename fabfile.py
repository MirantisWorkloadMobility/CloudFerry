import yaml
from fabric.api import task, env
from utils import log_step, get_log
from Scheduler import Scheduler
from Namespace import Namespace
from TaskInitMigrate import TaskInitMigrate
from TaskExportResource import SuperTaskExportResource

env.forward_agent = True
env.user = 'root'

LOG = get_log(__name__)


@log_step(LOG)
def search_instances_by_search_opts(config, exporter):
    for instance_search_opts in config['instances']:
        for instance in exporter.find_instances(instance_search_opts):
            yield instance


@log_step(LOG)
def migrate_one_instance(instance, exporter, importer):
    data = exporter.export(instance)
    importer.upload(data)


@task
def migrate(name_config, name_instance=None):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    namespace = Namespace({'name_config': name_config,
                           'name_instance': name_instance})
    scheduler = Scheduler(namespace)
    scheduler.addTask(TaskInitMigrate())
    scheduler.addTask(SuperTaskExportResource())
    scheduler.run()
    print scheduler.tasks_runned
    # res_importer.upload(resources)
    # LOG.info("Migrating all instance by search opts")
    # for instance in search_instances_by_search_opts(config, inst_exporter):
    #     LOG.debug("Migrate instance %s", instance)
    #     migrate_one_instance(instance, inst_exporter, inst_importer)

@task
def clean_dest_cloud(name_config, delete_image=False):
    LOG.info("Init config migrate")
    _, (_, _), (_, importer) = init_migrate(name_config)
    importer.clean_cloud(delete_image)
