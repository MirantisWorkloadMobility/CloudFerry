from migrationlib.os.exporter import osExporter, osResourceExporter
from migrationlib.os.importer import osImporter, osResourceImporter
from scheduler.Task import Task
from fabric.api import env
from utils import get_log
import yaml

__author__ = 'mirrorcoder'

LOG = get_log(__name__)


class TaskInitMigrate(Task):

    @staticmethod
    def get_exporter(config):
        return {
            'os': lambda info: (osResourceExporter.ResourceExporter(info), osExporter.Exporter(info))
        }[config['clouds']['from']['type']](config)

    @staticmethod
    def get_importer(config):
        return {
            'os': lambda info: (osResourceImporter.ResourceImporter(info), osImporter.Importer(info))
        }[config['clouds']['to']['type']](config)

    @staticmethod
    def init_migrate(name_config):
        config = yaml.load(open(name_config, 'r'))
        exporter = TaskInitMigrate.get_exporter(config)
        importer = TaskInitMigrate.get_importer(config)
        return config, exporter, importer

    def run(self, __name_config__="", name_instance="", **kwargs):
        LOG.info("Init migrationlib config")
        config, (res_exporter, inst_exporter), (res_importer, inst_importer) = \
            TaskInitMigrate.init_migrate(__name_config__)
        if name_instance:
            config['instances'] = [{'name': name_instance}]
        env.key_filename = config['key_filename']['name']
        return {
            'config': config,
            'res_exporter': res_exporter,
            'res_importer': res_importer,
            'inst_exporter': inst_exporter,
            'inst_importer': inst_importer
        }
