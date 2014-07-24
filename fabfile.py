import yaml
import osResourceTransfer
import osExporter
import osImporter
from fabric.api import task, env
import logging

env.forward_agent = True
env.user = 'root'
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('migrate.log')
LOG.addHandler(hdlr)


def get_exporter(config):
    return {
        'os': lambda info: (osResourceTransfer.ResourceExporter(info), osExporter.Exporter(info))
    }[config['clouds']['from']['type']](config)


def get_importer(config):
    return {
        'os': lambda info: (osResourceTransfer.ResourceImporter(info), osImporter.Importer(info))
    }[config['clouds']['to']['type']](config)


def init_migrate(name_config):
    config = yaml.load(open(name_config, 'r'))
    exporter = get_exporter(config)
    importer = get_importer(config)
    return config, exporter, importer


def search_instances_by_search_opts(config, exporter):
    for instance_search_opts in config['instances']:
        for instance in exporter.find_instances(instance_search_opts):
            yield instance


def migrate_one_instance(instance, exporter, importer):
    data = exporter.export(instance)
    importer.upload(data)


@task
def migrate(name_config):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    LOG.info("Init migration config")
    config, (res_exporter, inst_exporter), (res_importer, inst_importer) = init_migrate(name_config)
    env.key_filename = config['key_filename']['name']
    LOG.info("Migrating all resources")
    resources = res_exporter.get_tenants()\
                            .build()
    res_importer.upload(resources)
    LOG.info("Migrating all instance by search opts")
    for instance in search_instances_by_search_opts(config, inst_exporter):
        LOG.debug("Migrate instance %s", instance)
        migrate_one_instance(instance, inst_exporter, inst_importer)

@task
def clean_dest_cloud(name_config, delete_image=False):
    LOG.info("Init config migrate")
    _, (_, _), (_, importer) = init_migrate(name_config)
    importer.clean_cloud(delete_image)
