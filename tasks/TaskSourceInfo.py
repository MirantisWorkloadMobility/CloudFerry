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
    def get_tenant_obj(config, tenant=None):
        if tenant:
            config['tenant'] = tenant.name
        return osInfo.MainInfoResource(config)

    def run(self, name_config="", **kwargs):
        LOG.info("Init migrationlib config")
        config = TaskSourceInfo.init_source_config(name_config)
        admin_tenant = TaskSourceInfo.get_tenant_obj(config)
        tenants_list = admin_tenant.info_tenants_list()
        tenants_info = dict()
        for tenant in tenants_list:
            if not tenant.name in ['service', 'services','invisible_to_admin']:
                tenants_info[tenant.name] = TaskSourceInfo.get_tenant_obj(config, tenant)
        return {
            'config': config,
            'main_tenant': admin_tenant,
            'tenants_list': tenants_list,
            'tenants_info': tenants_info
        }