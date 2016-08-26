# Copyright (c) 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.
from cloudferry.lib.os import clients
from cloudferry.lib.os.migrate import base
from cloudferry.model import identity

from keystoneclient import exceptions


class CreateTenant(base.MigrationTask):
    default_provides = ['dst_object']

    def migrate(self, source_obj, *args, **kwargs):
        identity_client = clients.identity_client(self.dst_cloud)
        try:
            destination_obj = clients.retry(
                identity_client.tenants.create, source_obj.name,
                description=source_obj.description, enabled=source_obj.enabled,
                expected_exceptions=[exceptions.Conflict])
            self.created_object = destination_obj
        except exceptions.Conflict:
            for tenant_obj in clients.retry(identity_client.tenants.list):
                if tenant_obj.name.lower() == source_obj.name.lower():
                    destination_obj = tenant_obj
                    break
            else:
                raise base.AbortMigration('Invalid state')
        destination = self.load_from_cloud(
            identity.Tenant, self.dst_cloud, destination_obj)
        return dict(dst_object=destination)

    def revert(self, *args, **kwargs):
        if self.created_object is not None:
            identity_client = clients.identity_client(self.dst_cloud)
            clients.retry(identity_client.tenants.delete, self.created_object)
        super(CreateTenant, self).revert(*args, **kwargs)


class TenantMigrationFlowFactory(base.MigrationFlowFactory):
    migrated_class = identity.Tenant

    def create_flow(self, config, migration, obj):
        return [
            CreateTenant(config, migration, obj),
            base.RememberMigration(config, migration, obj),
        ]
