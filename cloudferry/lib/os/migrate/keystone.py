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
from cloudferry.lib.os.discovery import keystone
from cloudferry.lib.os.migrate import base


class CreateTenant(base.MigrationTask):
    default_provides = ['dst_object']

    @property
    def dst_identity(self):
        cloud = self.config.clouds[self.migration.destination]
        return clients.identity_client(cloud)

    def migrate(self, *args, **kwargs):
        source = self.src_object
        dst_cloud = self.config.clouds[self.migration.destination]
        self.created_object = self.dst_identity.tenants.create(
            source.name, description=source.description,
            enabled=source.enabled)
        destination = keystone.Tenant.load_from_cloud(
            dst_cloud, self.created_object)
        return dict(dst_object=destination)

    def revert(self, *args, **kwargs):
        if self.created_object is not None:
            # TODO: retry delete
            self.dst_identity.tenants.delete(self.created_object)


class TenantMigrationFlowFactory(base.MigrationFlowFactory):
    migrated_class = keystone.Tenant

    def create_flow(self, config, migration, obj):
        return [
            CreateTenant(obj, config, migration),
            base.RememberMigration(obj, config, migration),
        ]
