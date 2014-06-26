import yaml
import osExporter
import osImporter
from fabric.api import task, env
import logging

env.forward_agent = True
env.user = 'root'
LOG = logging.getLogger(__name__)


def get_exporter(cloud_info):
    return {
        'os': lambda info: osExporter.Exporter(info)
    }[cloud_info['type']](cloud_info)


def get_importer(cloud_info):
    return {
        'os': lambda info: osImporter.Importer(info)
    }[cloud_info['type']](cloud_info)

def init_migrate(name_config):
    config = yaml.load(open(name_config, 'r'))
    exporter = get_exporter(config['clouds']['from'])
    importer = get_importer(config['clouds']['to'])
    return config, exporter, importer


def search_instances_by_search_opts(config, exporter):
    for instance_search_opts in config['instances']:
        for instance in exporter.find_instances(instance_search_opts):
            yield instance


def migrate_one_instance(instance, exporter, importer, config_from):
    data = exporter.export(instance)
    importer.upload(data, config_from)


@task
def migrate(name_config):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    LOG.info("Init config migrate")
    config, exporter, importer = init_migrate(name_config)
    env.key_filename = config['key_filename']['name']
    LOG.info("Migrating all instance by search opts")
    for instance in search_instances_by_search_opts(config, exporter):
        LOG.debug("Migrate instance %s", instance)
        migrate_one_instance(instance, exporter, importer, config['clouds']['from'])