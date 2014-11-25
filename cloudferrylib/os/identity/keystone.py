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

from cloudferrylib.base import identity
from keystoneclient.v2_0 import client as keystone_client
from cloudferrylib.utils import Postman, Templater, GeneratorPassword

NOVA_SERVICE = 'nova'


class KeystoneIdentity(identity.Identity):
    """The main class for working with OpenStack Keystone Identity Service."""

    def __init__(self, config, cloud):
        super(KeystoneIdentity, self).__init__()
        self.config = config
        self.keystone_client = self.get_client()
        self.mysql_connector = cloud.mysql_connector
        self.cloud = cloud
        self.postman = None
        if self.config['mail']['server'] != "-":
            self.postman = Postman(self.config['mail']['username'],
                                   self.config['mail']['password'],
                                   self.config['mail']['from_addr'],
                                   self.config['mail']['server'])
        self.templater = Templater()
        self.generator = GeneratorPassword()

    def read_info(self, **kwargs):
        info = {'identity': {'tenants': [],
                             'users': [],
                             'roles': []}}

        for tenant in self.get_tenants_list():
            info['identity']['tenants'].append(
                {'tenant': {'name': tenant.name,
                            'id': tenant.id,
                            'description': tenant.description},
                 'meta': {}})
        overwirte_user_passwords = self.config['migrate'][
            'overwrite_user_passwords']
        for user in self.get_users_list():
            info['identity']['users'].append(
                {'user': {'name': user.name,
                          'id': user.id,
                          'email': user.email,
                          'tenantId': user.tenantId},
                 'meta': {
                     'overwrite_password': overwirte_user_passwords}})

        for role in self.get_roles_list():
            info['identity']['roles'].append(
                {'role': {'name': role.name,
                          'id': role},
                 'meta': {}})

        info['identity']['user_tenants_roles'] = self._get_user_tenants_roles()
        if self.config['migrate']['keep_user_passwords']:
            info['identity']['user_passwords'] = self._get_user_passwords()
        return info

    def deploy(self, info):
        print 'Deploy started'
        tenants = info['identity']['tenants']
        users = info['identity']['users']
        roles = info['identity']['user_tenants_roles']

        self._deploy_tenants(tenants)
        self._deploy_roles(info['identity']['roles'])
        self._deploy_users(users, tenants)
        if self.config['migrate']['keep_user_passwords']:
            passwords = info['identity']['user_passwords']
            self._upload_user_passwords(users, passwords)
        self._upload_user_tenant_roles(roles, users, tenants)
        print 'Finished'

    def get_client(self):
        """ Getting keystone client """

        ks_client_for_token = keystone_client.Client(
            username=self.config['cloud']['user'],
            password=self.config['cloud']['password'],
            tenant_name=self.config['cloud']['tenant'],
            auth_url="http://" + self.config['cloud']['host'] + ":35357/v2.0/")

        return keystone_client.Client(
            token=ks_client_for_token.auth_ref['token']['id'],
            endpoint="http://" + self.config['cloud']['host'] + ":35357/v2.0/")

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

    def get_tenants_func(self):
        tenants = {tenant.id: tenant.name for tenant in self.get_tenants_list()}

        def func(tenant_id):
            return getattr(tenants, tenant_id, 'admin')

        return func

    def get_tenant_id_by_name(self, name):
        for tenant in self.get_tenants_list():
            if tenant.name == name:
                return tenant.id
        return None

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

    def roles_for_user(self, user_id, tenant_id):
        """ Getting list of user roles for tenant """

        return self.keystone_client.roles.roles_for_user(user_id, tenant_id)

    def create_role(self, role_name):
        """ Create new role in keystone. """

        return self.keystone_client.roles.create(role_name)

    def create_tenant(self, tenant_name, description=None, enabled=True):
        """ Create new tenant in keystone. """

        return self.keystone_client.tenants.create(tenant_name=tenant_name,
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

    def _deploy_tenants(self, tenants):
        dst_tenants = {tenant.name: tenant.id for tenant in
                       self.get_tenants_list()}
        for _tenant in tenants:
            tenant = _tenant['tenant']
            if tenant['name'] not in dst_tenants:
                _tenant['meta']['new_id'] = self.create_tenant(tenant['name'],
                                                               tenant[
                                                                   'description']).id
            else:
                _tenant['meta']['new_id'] = dst_tenants[tenant['name']]

    def _deploy_users(self, users, tenants):
        dst_users = {user.name: user.id for user in self.get_users_list()}
        tenant_mapped_ids = {tenant['tenant']['id']: tenant['meta']['new_id']
                             for tenant in tenants}

        keep_passwd = self.config['migrate']['keep_user_passwords']
        overwrite_passwd = self.config['migrate']['overwrite_user_passwords']
        for _user in users:
            user = _user['user']
            password = self._generate_password()

            if user['name'] in dst_users:
                _user['meta']['new_id'] = dst_users[user['name']]
                if overwrite_passwd and not keep_passwd:
                    self.update_user(_user['meta']['new_id'], password=password)
                    self._passwd_notification(user['email'], user['name'],
                                              password)
                continue

            tenant_id = tenant_mapped_ids[user['tenantId']]
            _user['meta']['new_id'] = self.create_user(user['name'], password,
                                                       user['email'],
                                                       tenant_id).id
            if self.config['migrate']['keep_user_passwords']:
                _user['meta']['overwrite_password'] = True
            else:
                self._passwd_notification(user['email'], user['name'], password)

    def _passwd_notification(self, email, name, password):
        if not self.postman:
            return
        template = 'templates/email.html'
        self._send_msg(email, 'New password notification',
                       self._render_template(template,
                                             {'name': name,
                                              'password': password}))

    def _deploy_roles(self, roles):
        dst_roles = {role.name: role.id for role in self.get_roles_list()}
        for _role in roles:
            role = _role['role']
            if role['name'] not in dst_roles:
                _role['meta']['new_id'] = self.create_role(role['name']).id
            else:
                _role['meta']['new_id'] = dst_roles[role['name']]

    def _get_user_passwords(self):
        info = {}
        for user in self.get_users_list():
            for password in self.mysql_connector.execute(
                    "SELECT password FROM user WHERE id = :user_id",
                    user_id=user.id):
                info[user.name] = password[0]

        return info

    def _get_user_tenants_roles(self):
        user_tenants_roles = {}
        tenants = self.get_tenants_list()
        for user in self.get_users_list():
            user_tenants_roles[user.name] = {}
            for tenant in tenants:
                roles = []
                for role in self.roles_for_user(user.id, tenant.id):
                    roles.append({'role': {'name': role.name, 'id': role.id}})
                user_tenants_roles[user.name][tenant.name] = roles
        return user_tenants_roles

    def _upload_user_passwords(self, users, user_passwords):
        for _user in users:
            user = _user['user']
            if not _user['meta']['overwrite_password']:
                continue
            self.mysql_connector.execute(
                "UPDATE user SET password = :password WHERE id = :user_id",
                user_id=_user['meta']['new_id'],
                password=user_passwords[user['name']])

    def _upload_user_tenant_roles(self, user_tenants_roles, users, tenants):
        roles_id = {role.name: role.id for role in self.get_roles_list()}

        for _user in users:
            user = _user['user']
            # FIXME should be deleted after determining how
            # to change self role without logout
            if user['name'] == self.keystone_client.username:
                continue
            for _tenant in tenants:
                tenant = _tenant['tenant']
                exists_roles = [role.name for role in
                                self.roles_for_user(_user['meta']['new_id'],
                                                    _tenant['meta']['new_id'])]
                for _role in user_tenants_roles[user['name']][tenant['name']]:
                    role = _role['role']
                    if role['name'] in exists_roles:
                        continue
                    self.keystone_client.roles.add_user_role(
                        _user['meta']['new_id'], roles_id[role['name']],
                        _tenant['meta']['new_id'])

    def _generate_password(self):
        return self.generator.get_random_password()

    def _send_msg(self, to, subject, msg):
        if self.postman:
            with self.postman as p:
                p.send(to, subject, msg)

    def _render_template(self, name_file, args):
        if self.templater:
            return self.templater.render(name_file, args)
        else:
            return None
