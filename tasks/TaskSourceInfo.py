import yaml

from migrationlib.os.exporter import osInfo
from utils import get_log
from scheduler.Task import Task


LOG = get_log(__name__)

class TaskSourceInfo(Task):

    @staticmethod
    def init_source_config(name_config):
        config = yaml.load(open(name_config, 'r'))
        return config['clouds']['source']

    @staticmethod
    def get_main_tenant(config):
        return osInfo.MainInfoResource(config)

    @staticmethod
    def get_info_tenant_list(tenant, config):
        return osInfo.InfoResource(tenant, config)

    def run(self, name_config="", **kwargs):
        LOG.info("Init migrationlib config")
        config = TaskSourceInfo.init_source_config(name_config)
        main_tenant = TaskSourceInfo.get_main_tenant(config)
        info_tenant_list = dict()
        print main_tenant.info_tenants_list()
        for tenant in main_tenant.info_tenants_list():
            if tenant.name in ['service', 'service','invisible_to_admin']:
               continue
            print tenant
            print tenant.name
            info_tenant_list[tenant.name] = TaskSourceInfo.get_info_tenant_list(tenant, config)
        return {
            'config': config,
            'main_tenant': main_tenant,
            'info_tenant_list': info_tenant_list
        }



