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
import sqlalchemy

from cloudferrylib.base import identity
from keystoneclient.v2_0 import client as keystone_client
from utils import Postman, Templater, GeneratorPassword

NOVA_SERVICE = 'nova'


class KeystoneIdentity(identity.Identity):
    """The main class for working with Openstack Keystone Identity Service."""

    def __init__(self, config, position):
        super(KeystoneIdentity, self).__init__()
        self.config = config
        self.position = position
        self.keystone_client = self.get_client()
        self.keystone_db_conn_url = self.compose_keystone_db_conn_url()
        self.postman = Postman(self.config.migrate.mail_username,
                               self.config.migrate.mail_password,
                               self.config.migrate.mail_from_addr,
                               self.config.migrate.mail_server)
        self.templater = Templater()
        self.generator = GeneratorPassword()

    def read_info(self, opts=None):
        opts = {} if not opts else opts
        resource = {'tenants': self.get_tenants_list(),
                    'users': self.get_users_list(),
                    'roles': self.get_roles_list(),
                    'user_tenants_roles': self.__get_user_tenants_roles()}
        if self.config.migrate.keep_user_passwords:
            resource['user_passwords'] = self.__get_user_passwords()
        return resource

    def deploy(self, info):
        self.__deploy_tenants(info['tenants'])
        self.__deploy_roles(info['roles'])
        created = self.__deploy_users(info['users'], info['tenants'])
        if self.config.migrate.keep_user_passwords:
            self.__upload_user_passwords(created, info['user_passwords'])
        self.__upload_user_tenant_roles(info['user_tenants_roles'])

    def __deploy_users(self, users, tenants):
        exists = [user.name for user in self.get_users_list()]
        dst_tenant_ids = {tenant.name: tenant.id for tenant in self.get_tenants_list()}
        src_tenant_names = {tenant.id: tenant.name for tenant in tenants}
        template = 'templates/email.html'
        created = []
        for user in users:
            if user.name in exists:
                continue
            tenant_name = src_tenant_names[user.tenantId]
            tenant_id = dst_tenant_ids[tenant_name]
            password = 'password' if self.config.migrate.keep_user_passwords else self.__generate_password()
            self.create_user(user.name, password, user.email, tenant_id)
            created.append(user.name)
            if not self.config.migrate.keep_user_passwords:
                self.__send_msg(user.email,
                                'New password notification',
                                self.__render_template(template,
                                                       {'name': user.name,
                                                        'password': password}))
        return created

    def __deploy_roles(self, roles):
        exists = [role.name for role in self.get_roles_list()]
        for role in roles:
            if role.name not in exists:
                self.create_role(role.name)

    def __deploy_tenants(self, tenants):
        exists = [tenant.name for tenant in self.get_tenants_list()]
        for tenant in tenants:
            if tenant.name not in exists:
                self.create_tenant(tenant.name, tenant.description)

    def get_client(self):
        """ Getting keystone client """
        credentials = getattr(self.config, self.position)
        print credentials.host
        ks_client_for_token = keystone_client.Client(
            username=credentials.user,
            password=credentials.password,
            tenant_name=credentials.tenant,
            auth_url="http://" + credentials.host + ":35357/v2.0/")

        return keystone_client.Client(
            token=ks_client_for_token.auth_ref["token"]["id"],
            endpoint="http://" + credentials.host + ":35357/v2.0/")

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

    def compose_keystone_db_conn_url(self):

        """ Compose keystone database connection url for SQLAlchemy """
        credentials = getattr(self.config, "%s_mysql" % self.position)
        return '{}://{}:{}@{}/keystone'.format(credentials.connection,
                                               credentials.user,
                                               credentials.password,
                                               credentials.host)

    def __get_user_passwords(self):
        info = {}
        with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
            for user in self.get_users_list():
                for password in connection.execute(sqlalchemy.text("SELECT password FROM user WHERE id = :user_id"),
                                                   user_id=user.id):
                    info[user.name] = password[0]
        return info

    def __get_user_tenants_roles(self):
        roles = {}
        tenants = self.get_tenants_list()
        for user in self.get_users_list():
            roles[user.name] = {}
            for tenant in tenants:
                roles[user.name][tenant.name] = self.keystone_client.roles.roles_for_user(user.id, tenant.id)
        return roles

    def __upload_user_passwords(self, users, user_passwords):
        with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
            for user in self.keystone_client.users.list():
                if user.name in users:
                    connection.execute(sqlalchemy.text("UPDATE user SET password = :password WHERE id = :user_id"),
                                       user_id=user.id,
                                       password=user_passwords[user.name])

    def __upload_user_tenant_roles(self, user_tenants_roles):
        users_id_by_name = {user.name: user.id for user in self.get_users_list()}
        tenants_id_by_name = {tenant.name: tenant.id for tenant in self.get_tenants_list()}
        roles_id_by_name = {role.name: role.id for role in self.get_roles_list()}
        for user_name in user_tenants_roles:
            # FIXME should be deleted after determining how to change self role without logout
            if user_name == self.keystone_client.username:
                continue
            for tenant_name in user_tenants_roles[user_name]:
                exists = [role.name for role in self.keystone_client.roles.roles_for_user(
                    users_id_by_name[user_name],
                    tenants_id_by_name[tenant_name])]
                for role in user_tenants_roles[user_name][tenant_name]:
                    if role.name not in exists:
                        self.keystone_client.roles.add_user_role(users_id_by_name[user_name],
                                                                 roles_id_by_name[role.name],
                                                                 tenants_id_by_name[tenant_name])

    def __generate_password(self):
        return self.generator.get_random_password()

    def __send_msg(self, to, subject, msg):
        if self.postman:
            with self.postman as p:
                p.send(to, subject, msg)

    def __render_template(self, name_file, args):
        if self.templater:
            return self.templater.render(name_file, args)
        else:
            return None
