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

    @log_step(3, LOG)
    def __upload_tenants(self, tenants):
        # do not import a tenant if one with the same name already exists
        existing = frozenset((t.name for t in self.keystone_client.tenants.list()))
        for tenant in filter(lambda t: t.name not in existing, tenants):
            self.keystone_client.tenants.create(id=tenant.id,
                                                tenant_name=tenant.name,
                                                description=tenant.description,
                                                enabled=tenant.enabled)
