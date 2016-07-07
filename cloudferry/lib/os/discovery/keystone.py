# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from keystoneclient import exceptions

from cloudferry import discover
from cloudferry import model
from cloudferry.model import identity
from cloudferry.lib.os import clients

LOG = logging.getLogger(__name__)


class TenantDiscoverer(discover.Discoverer):
    discovered_class = identity.Tenant

    def discover_all(self):
        identity_client = clients.identity_client(self.cloud)
        raw_tenants = self.retry(identity_client.tenants.list,
                                 returns_iterable=True)
        with model.Session() as session:
            for raw_tenant in raw_tenants:
                session.store(self.load_from_cloud(raw_tenant))

    def discover_one(self, uuid):
        identity_client = clients.identity_client(self.cloud)
        try:
            raw_tenant = self.retry(identity_client.tenants.get, uuid,
                                    expected_exceptions=[exceptions.NotFound])
            tenant = self.load_from_cloud(raw_tenant)
            with model.Session() as session:
                session.store(tenant)
                return tenant
        except exceptions.NotFound:
            raise discover.NotFound()

    def load_from_cloud(self, data):
        return identity.Tenant.load({
            'object_id': self.make_id(data.id),
            'name': data.name,
            'enabled': data.enabled,
            'description': data.description,
        })
