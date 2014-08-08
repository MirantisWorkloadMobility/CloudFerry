from Task import Task
from utils import *
from fabric.api import env
import yaml
import osResourceTransfer
import osExporter

import osImporter
__author__ = 'mirrorcoder'

LOG = get_log(__name__)


class TaskInitMigrate(Task):

    @staticmethod
    def get_exporter(config):
        return {
            'os': lambda info: (osResourceTransfer.ResourceExporter(info), osExporter.Exporter(info))
        }[config['clouds']['from']['type']](config)

    @staticmethod
    def get_importer(config):
        return {
            'os': lambda info: (osResourceTransfer.ResourceImporter(info), osImporter.Importer(info))
        }[config['clouds']['to']['type']](config)

    @staticmethod
    def init_migrate(name_config):
        config = yaml.load(open(name_config, 'r'))
        exporter = TaskInitMigrate.get_exporter(config)
        importer = TaskInitMigrate.get_importer(config)
        return config, exporter, importer

    def func(self, name_config="", name_instance="", **kwargs):
        print name_config, name_instance
        LOG.info("Init migration config")
        config, (res_exporter, inst_exporter), (res_importer, inst_importer) = TaskInitMigrate.init_migrate(name_config)
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
