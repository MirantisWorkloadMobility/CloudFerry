# Copyright (c) 2014 Mirantis Inc.
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
# See the License for the specific language governing permissions and
# limitations under the License.

from cloudferrylib.base import Identity
from keystoneclient.v2_0 import client as keystone_client

NOVA_SERVICE = 'nova'


class KeystoneIdentity(Identity.Identity):
    """The main class for working with Openstack Keystone Identity Service."""

    def __init__(self, config):
        super(KeystoneIdentity, self).__init__()
        self.config = config
        self.keystone_client = self.get_client()

    def get_client(self):
        """ Getting keystone client """

        ks_client_for_token = keystone_client.Client(
            username=self.config["user"],
            password=self.config["password"],
            tenant_name=self.config["tenant"],
            auth_url="http://" + self.config["host"] + ":35357/v2.0/")

        return keystone_client.Client(
            token=ks_client_for_token.auth_ref["token"]["id"],
            endpoint="http://" + self.config["host"] + ":35357/v2.0/")

    def get_service_name_by_type(self, service_type):
        """Getting service_name from keystone. """

        for service in self.get_services_list():
            if service.type == service_type:
                return service.name
        return NOVA_SERVICE

    def get_public_endpoint_service_by_id(self, service_id):
        """Getting endpoint public URL from keystone. """

        for endpoint in self.keystone_client.endpoints.list():
            if endpoint.service_id == service_id:
                return endpoint.publicurl

    def get_service_id(self, service_name):
        """Getting service_id from keystone. """

        for service in self.get_services_list():
            if service.name == service_name:
                return service.id

    def get_endpoint_by_service_name(self, service_name):
        """ Getting endpoint public URL by service name from keystone. """

        service_id = self.get_service_id(service_name)
        return self.get_public_endpoint_service_by_id(service_id)

    def get_tenant_by_name(self, tenant_name):
        """ Getting tenant by name from keystone. """

        for tenant in self.get_tenants_list():
            if tenant.name == tenant_name:
                return tenant

    def get_tenant_by_id(self, tenant_id):
        """ Getting tenant by id from keystone. """

        return self.keystone_client.tenants.get(tenant_id)

    def get_services_list(self):
        """ Getting list of available services from keystone. """

        return self.keystone_client.services.list()

    def get_tenants_list(self):
        """ Getting list of tenants from keystone. """

        return self.keystone_client.tenants.list()

    def get_users_list(self):
        """ Getting list of users from keystone. """

        return self.keystone_client.users.list()

    def get_roles_list(self):
        """ Getting list of available roles from keystone. """

        return self.keystone_client.roles.list()

    def create_role(self, role_name):
        """ Create new role in keystone. """

        self.keystone_client.roles.create(role_name)

    def create_tenant(self, tenant_name, description=None, enabled=True):
        """ Create new tenant in keystone. """

        self.keystone_client.tenants.create(tenant_name=tenant_name,
                                            description=description,
                                            enabled=enabled)

    def create_user(self, name, password=None, email=None, tenant_id=None,
                    enabled=True):
        """ Create new user in keystone. """

        return self.keystone_client.users.create(name=name,
                                                 password=password,
                                                 email=email,
                                                 tenant_id=tenant_id,
                                                 enabled=enabled)

    def update_tenant(self, tenant_id, tenant_name=None, description=None,
                      enabled=None):
        """Update a tenant with a new name and description."""

        return self.keystone_client.tenants.update(tenant_id,
                                                   tenant_name=tenant_name,
                                                   description=description,
                                                   enabled=enabled)

    def update_user(self, user, **kwargs):
        """Update user data.

        Supported arguments include ``name``, ``email``, and ``enabled``.
        """

        return self.keystone_client.users.update(user, **kwargs)

    def get_auth_token_from_user(self):
        return self.keystone_client.auth_token_from_user
