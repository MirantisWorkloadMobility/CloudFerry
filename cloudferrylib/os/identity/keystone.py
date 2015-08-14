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


import pika

import keystoneclient
from keystoneclient.v2_0 import client as keystone_client

import cfglib
from cloudferrylib.base import identity
from cloudferrylib.utils import GeneratorPassword
from cloudferrylib.utils import Postman
from cloudferrylib.utils import Templater
from cloudferrylib.utils import utils as utl


LOG = utl.get_log(__name__)


class AddAdminUserToNonAdminTenant(object):
    """Temporarily adds admin user to non-admin tenant when necessary.

    Use when any openstack object must be created in specific tenant. If
    admin user is already added to the tenant as tenant's member - nothing
    happens. Otherwise admin user is added to a tenant on block entrance, and
    removed on exit.

    When this class is in use, make sure *all* your openstack clients generate
    new auth token on *each* openstack API call, because when user gets added
    to a tenant as a member, all it's tokens get revoked.

    Usage:
     with AddAdminUserToNonAdminTenant():
        your_operation_from_admin_user()
    """

    def __init__(self, keystone, admin_user, tenant, member_role='admin'):
        """
        :tenant: can be either tenant name or tenant ID
        """

        self.keystone = keystone
        try:
            self.tenant = self.keystone.tenants.find(name=tenant)
        except keystoneclient.exceptions.NotFound:
            self.tenant = self.keystone.tenants.find(id=tenant)
        self.user = self.keystone.users.find(name=admin_user)
        self.role = self.keystone.roles.find(name=member_role)
        self.already_member = False

    def __enter__(self):
        roles = self.keystone.roles.roles_for_user(user=self.user,
                                                   tenant=self.tenant)

        for role in roles:
            if role.name == self.role.name:
                # do nothing if user is already member of a tenant
                self.already_member = True
                return
        LOG.debug("Adding %s user to tenant %s as %s",
                  self.user.name, self.tenant.name, self.role.name)
        self.keystone.roles.add_user_role(user=self.user,
                                          role=self.role,
                                          tenant=self.tenant)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.already_member:
            LOG.debug("Removing %s user from tenant %s",
                      self.user.name, self.tenant.name)
            self.keystone.roles.remove_user_role(user=self.user,
                                                 role=self.role,
                                                 tenant=self.tenant)


class KeystoneIdentity(identity.Identity):
    """The main class for working with OpenStack Keystone Identity Service."""

    def __init__(self, config, cloud):
        super(KeystoneIdentity, self).__init__()
        self.config = config
        self.mysql_connector = cloud.mysql_connector
        self.cloud = cloud
        self.filter_tenant_id = None
        self.postman = None
        if self.config.mail.server != "-":
            self.postman = Postman(self.config['mail']['username'],
                                   self.config['mail']['password'],
                                   self.config['mail']['from_addr'],
                                   self.config['mail']['server'])
        self.templater = Templater()
        self.generator = GeneratorPassword()

    @property
    def keystone_client(self):
        return self.proxy(self._get_client_by_creds(), self.config)

    @staticmethod
    def convert(identity_obj, cfg):
        """Convert OpenStack Keystone object to CloudFerry object.

        :param identity_obj:    Direct OpenStack Keystone object to convert,
                                supported objects: tenants, users and roles;
        :param cfg:             Cloud config.
        """

        if isinstance(identity_obj, keystone_client.tenants.Tenant):
            return {'tenant': {'name': identity_obj.name,
                               'id': identity_obj.id,
                               'description': identity_obj.description},
                    'meta': {}}

        elif isinstance(identity_obj, keystone_client.users.User):
            overwirte_user_passwords = cfg.migrate.overwrite_user_passwords
            return {'user': {'name': identity_obj.name,
                             'id': identity_obj.id,
                             'email': identity_obj.email,
                             'tenantId': identity_obj.tenantId},
                    'meta': {
                        'overwrite_password': overwirte_user_passwords}}

        elif isinstance(identity_obj, keystone_client.roles.Role):
            return {'role': {'name': identity_obj.name,
                             'id': identity_obj},
                    'meta': {}}

        LOG.error('KeystoneIdentity converter has received incorrect value. '
                  'Please pass to it only tenants, users or role objects.')
        return None

    def read_info(self, **kwargs):
        info = {'tenants': [],
                'users': [],
                'roles': []}

        if kwargs.get('tenant_id'):
            self.filter_tenant_id = kwargs['tenant_id'][0]

        tenant_list = self.get_tenants_list()
        for tenant in tenant_list:
            tnt = self.convert(tenant, self.config)
            info['tenants'].append(tnt)

        user_list = self.get_users_list()
        for user in user_list:
            usr = self.convert(user, self.config)
            info['users'].append(usr)

        for role in self.get_roles_list():
            rl = self.convert(role, self.config)
            info['roles'].append(rl)

        info['user_tenants_roles'] = \
             self._get_user_tenants_roles(tenant_list, user_list)
        if self.config['migrate']['keep_user_passwords']:
            info['user_passwords'] = self._get_user_passwords()
        return info

    def deploy(self, info):
        LOG.info("Identity objects deployment started")
        tenants = info['tenants']
        users = info['users']
        roles = info['user_tenants_roles']

        self._deploy_tenants(tenants)
        self._deploy_roles(info['roles'])
        self._deploy_users(users, tenants)
        if not self.config.migrate.migrate_users:
            users = info['users'] = self._update_users_info(users)
        if self.config['migrate']['keep_user_passwords']:
            passwords = info['user_passwords']
            self._upload_user_passwords(users, passwords)
        self._upload_user_tenant_roles(roles, users, tenants)
        LOG.info("Done")

    def get_client(self):
        """ Getting keystone client using authentication with admin auth token.

        :return: OpenStack Keystone Client instance
        """

        return self.keystone_client

    def _get_client_by_creds(self):
        """Authenticating with a user name and password.

        :return: OpenStack Keystone Client instance
        """

        return keystone_client.Client(username=self.config.cloud.user,
                                      password=self.config.cloud.password,
                                      tenant_name=self.config.cloud.tenant,
                                      auth_url=self.config.cloud.auth_url)

    def get_endpoint_by_service_type(self, service_type, endpoint_type):
        """Getting endpoint URL by service type.

        :param service_type: OpenStack service type (image, compute etc.)
        :param endpoint_type: publicURL or internalURL

        :return: String endpoint of specified OpenStack service
        """

        return self.keystone_client.service_catalog.url_for(
            service_type=service_type,
            endpoint_type=endpoint_type)

    def get_tenants_func(self):
        tenants = {tenant.id: tenant.name for tenant in
                   self.get_tenants_list()}

        def func(tenant_id):
            return tenants.get(tenant_id, 'admin')

        return func

    def get_tenant_id_by_name(self, name):
        """ Getting tenant ID by name from keystone. """

        return self.keystone_client.tenants.find(name=name).id

    def get_tenant_by_name(self, tenant_name):
        """ Getting tenant by name from keystone. """

        for tenant in self.get_tenants_list():
            if tenant.name == tenant_name:
                return tenant

    def get_tenant_by_id(self, tenant_id):
        """ Getting tenant by id from keystone. """

        return self.keystone_client.tenants.get(tenant_id)

    def try_get_tenant_name_by_id(self, tenant_id, default=None):
        """ Same as `get_tenant_by_id` but returns `default` in case tenant
        ID is not present """
        try:
            return self.keystone_client.tenants.get(tenant_id).name
        except keystoneclient.exceptions.NotFound:
            LOG.warning("Tenant '%s' not found, returning default value = "
                        "'%s'", tenant_id, default)
            return default

    def get_services_list(self):
        """ Getting list of available services from keystone. """

        return self.keystone_client.services.list()

    def get_tenants_list(self):
        """ Getting list of tenants from keystone. """

        result = []
        ks_tenants = self.keystone_client.tenants
        if self.filter_tenant_id:
            result.append(ks_tenants.find(id=self.filter_tenant_id))
        else:
            result = ks_tenants.list()
        return result

    def get_users_list(self):
        """ Getting list of users from keystone. """

        if self.filter_tenant_id:
            tenant_id = self.filter_tenant_id
        else:
            tenant_id = None
        return self.keystone_client.users.list(tenant_id=tenant_id)

    def get_roles_list(self):
        """ Getting list of available roles from keystone. """

        return self.keystone_client.roles.list()

    def try_get_username_by_id(self, user_id, default=None):
        try:
            return self.keystone_client.users.get(user_id).name
        except keystoneclient.exceptions.NotFound:
            return default

    def try_get_user_by_id(self, user_id, default=None):
        if default is None:
            admin_usr = \
                self.try_get_user_by_name(username=self.config.cloud.user)
            default = admin_usr.id
        try:
            return self.keystone_client.users.find(id=user_id)
        except keystoneclient.exceptions.NotFound:
            LOG.warning("User '%s' has not been found, returning default "
                        "value = '%s'", user_id, default)
            return self.keystone_client.users.find(id=default)

    def try_get_user_by_name(self, username, default=None):
        try:
            return self.keystone_client.users.find(name=username)
        except keystoneclient.exceptions.NotFound:
            LOG.warning("User '%s' has not been found, returning default "
                        "value = '%s'", username, default)
            return self.keystone_client.users.find(name=default)

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
        self.keystone_client.authenticate()
        return self.keystone_client.auth_token

    def _deploy_tenants(self, tenants):
        dst_tenants = {tenant.name: tenant.id for tenant in
                       self.get_tenants_list()}
        for _tenant in tenants:
            tenant = _tenant['tenant']
            if tenant['name'] not in dst_tenants:
                _tenant['meta']['new_id'] = self.create_tenant(
                    tenant['name'],
                    tenant['description']).id
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
                # Create users mapping
                _user['meta']['new_id'] = dst_users[user['name']]

                if overwrite_passwd and not keep_passwd:
                    self.update_user(_user['meta']['new_id'],
                                     password=password)
                    self._passwd_notification(user['email'], user['name'],
                                              password)
                continue

            if not self.config.migrate.migrate_users:
                continue

            tenant_id = tenant_mapped_ids[user['tenantId']]
            _user['meta']['new_id'] = self.create_user(user['name'], password,
                                                       user['email'],
                                                       tenant_id).id
            if self.config['migrate']['keep_user_passwords']:
                _user['meta']['overwrite_password'] = True
            else:
                self._passwd_notification(user['email'], user['name'],
                                          password)

    @staticmethod
    def _update_users_info(users):
        """
        Update users info.

        This method is needed for skip users, that have not been migrated to
        destination cloud and that do not exist there. So we leave information
        only about users with mapping and skip those, who don't have the same
        user on the destination cloud. This is done, because another tasks can
        use users mapping.

        :param users: OpenStack Keystone users info;
        :return: List with actual users info.
        """

        users_info = []
        for user in users:
            if user['meta'].get('new_id'):
                users_info.append(user)

        return users_info

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

    def _get_user_tenants_roles(self, tenant_list=None, user_list=None):
        if tenant_list is None:
            tenant_list = []
        if user_list is None:
            user_list = []
        user_tenants_roles = {}
        for user in user_list:
            user_tenants_roles[user.name] = {}
            for tenant in tenant_list:
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
        dst_users = {user.name: user.id for user in self.get_users_list()}

        for _user in users:
            user = _user['user']
            if user['name'] not in dst_users:
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

    def check_rabbitmq(self):
        credentials = pika.PlainCredentials(self.config.rabbit.user,
                                            self.config.rabbit.password)

        for host_with_port in self.config.rabbit.hosts.split(","):
            host, port = host_with_port.split(':')
            pika.BlockingConnection(
                pika.ConnectionParameters(host=host.strip(),
                                          port=int(port),
                                          credentials=credentials))


def get_dst_user_from_src_user_id(src_keystone, dst_keystone, src_user_id,
                                  fallback_to_admin=True):
    """Returns user from destination with the same name as on source. None if
    user does not exist"""
    try:
        src_user = src_keystone.keystone_client.users.find(id=src_user_id)
        src_user_name = src_user.name
    except keystoneclient.exceptions.NotFound:
        LOG.warning("User '%s' not found on SRC!", src_user_id)
        if fallback_to_admin:
            LOG.warning("Replacing user '%s' with SRC admin", src_user_id)
            src_user_name = cfglib.CONF.src.user
        else:
            return

    try:
        dst_user = dst_keystone.keystone_client.users.find(name=src_user_name)
        return dst_user
    except keystoneclient.exceptions.NotFound:
        LOG.warning("User '%s' not found on DST!", src_user_name)
        if fallback_to_admin:
            LOG.warning("Replacing user '%s' with DST admin", src_user_name)
            dst_user = dst_keystone.keystone_client.users.find(
                name=cfglib.CONF.dst.user)
            return dst_user
