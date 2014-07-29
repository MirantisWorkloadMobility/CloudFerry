"""
Package with OpenStack resources export/import utilities.
"""
import osCommon
from utils import log_step, get_log

LOG = get_log(__name__)


class ResourceExporter(osCommon.osCommon):
    """
    Exports various cloud resources (tenants, users, flavors, etc.) to a container
    to be later imported by ResourceImporter
    """

    def __init__(self, conf):
        self.data = dict()
        super(ResourceExporter, self).__init__(conf['clouds']['from'])

    @log_step(2, LOG)
    def get_flavors(self):
        self.data['flavors'] = self.nova_client.flavors.list(is_public=None)
        return self

    @log_step(2, LOG)
    def get_tenants(self):
        self.data['tenants'] = self.keystone_client.tenants.list()
        return self

    @log_step(2, LOG)
    def build(self):
        return self.data


class ResourceImporter(osCommon.osCommon):
    """
    Imports various cloud resources (tenants, users, flavors, etc.) from a container
    prepared by ResourceExporter
    """

    def __init__(self, conf):
        super(ResourceImporter, self).__init__(conf['clouds']['to'])

    @log_step(2, LOG)
    def upload(self, data):
        self.__upload_tenants(data['tenants'])
        self.__upload_flavors(data['flavors'])

    @log_step(3, LOG)
    def __upload_tenants(self, tenants):
        # do not import a tenant if one with the same name already exists
        existing = {t.name for t in self.keystone_client.tenants.list()}
        for tenant in tenants:
            if tenant.name not in existing:
                self.keystone_client.tenants.create(tenant_name=tenant.name,
                                                    description=tenant.description,
                                                    enabled=tenant.enabled)

    @log_step(3, LOG)
    def __upload_flavors(self, flavors):
        # do not import a flavor if one with the same name already exists
        existing = {f.name for f in self.nova_client.flavors.list(is_public=None)}
        for flavor in flavors:
            if flavor.name not in existing:
                self.nova_client.flavors.create(name=flavor.name,
                                                ram=flavor.ram,
                                                vcpus=flavor.vcpus,
                                                disk=flavor.disk,
                                                swap=flavor.swap,
                                                rxtx_factor=flavor.rxtx_factor,
                                                ephemeral=flavor.ephemeral,
                                                is_public=flavor.is_public)
