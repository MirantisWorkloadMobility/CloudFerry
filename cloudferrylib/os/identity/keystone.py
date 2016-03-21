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
import ast

from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v2_0 import client as keystone_client

import cfglib
from cloudferrylib.base import identity
from cloudferrylib.utils.cache import Cached
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import retrying
from cloudferrylib.utils.utils import GeneratorPassword
from cloudferrylib.utils.utils import Postman
from cloudferrylib.utils.utils import Templater
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl
from sqlalchemy.exc import ProgrammingError

LOG = log.getLogger(__name__)
NO_TENANT = ''


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
            with proxy_client.expect_exception(ks_exceptions.NotFound):
                self.tenant = find_by_name(
                    'tenant', self.keystone.tenants.list(), tenant)
        except ks_exceptions.NotFound:
            self.tenant = self.keystone.tenants.get(tenant)
        self.user = find_by_name(
            'user', self.keystone.users.list(), admin_user)
        self.role = find_by_name(
            'role', self.keystone.roles.list(), member_role)
        self.already_member = False

    def __enter__(self):
        roles = self.keystone.roles.roles_for_user(user=self.user,
                                                   tenant=self.tenant)

        for role in roles:
            if role.name.lower() == self.role.name.lower():
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


@Cached(getter='get_tenants_list', modifier='create_tenant')
class KeystoneIdentity(identity.Identity):

    """The main class for working with OpenStack Keystone Identity Service."""

    def __init__(self, config, cloud):
        super(KeystoneIdentity, self).__init__()
        self.config = config
        self.cloud = cloud
        self.filter_tenant_id = None
        self.postman = None
        if self.config.mail.server != "-":
            self.postman = Postman(self.config['mail']['username'],
                                   self.config['mail']['password'],
                                   self.config['mail']['from_addr'],
                                   self.config['mail']['server'])
        self.mysql_connector = cloud.mysql_connector('keystone')
        self.templater = Templater()
        self.generator = GeneratorPassword()
        self.defaults = {}

    @property
    def keystone_client(self):
        return self.proxy(self.get_client(), self.config)

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
            overwrite_user_passwords = cfg.migrate.overwrite_user_passwords
            return {'user': {'name': identity_obj.name,
                             'id': identity_obj.id,
                             'email': getattr(identity_obj, 'email', ''),
                             'tenantId': getattr(identity_obj, 'tenantId', '')
                             },
                    'meta': {
                        'overwrite_password': overwrite_user_passwords}}

        elif isinstance(identity_obj, keystone_client.roles.Role):
            return {'role': {'name': identity_obj.name,
                             'id': identity_obj},
                    'meta': {}}

        LOG.error('KeystoneIdentity converter has received incorrect value. '
                  'Please pass to it only tenants, users or role objects.')
        return None

    def has_tenants_by_id_cached(self):
        tenants = set([t.id for t in self.keystone_client.tenants.list()])

        def func(tenant_id):
            return tenant_id in tenants

        return func

    def read_info(self, **kwargs):
        info = {'tenants': [],
                'users': [],
                'roles': []}
        if kwargs.get('tenant_id'):
            self.filter_tenant_id = kwargs['tenant_id'][0]

        tenant_list = self._get_required_tenants_list()
        info['tenants'] = [self.convert(tenant, self.config)
                           for tenant in tenant_list]
        user_list = self.get_users_list()
        has_tenants_by_id_cached = self.has_tenants_by_id_cached()
        has_roles_by_ids_cached = self._get_user_roles_cached()
        for user in user_list:
            usr = self.convert(user, self.config)
            if has_tenants_by_id_cached(getattr(user, 'tenantId', '')):
                info['users'].append(usr)
            else:
                LOG.info("User's '%s' primary tenant '%s' is deleted, "
                         "finding out if user is a member of other tenants",
                         user.name, getattr(user, 'tenantId', ''))
                for t in tenant_list:
                    roles = has_roles_by_ids_cached(user.id, t.id)
                    if roles:
                        LOG.info("Setting tenant '%s' for user '%s' as "
                                 "primary", t.name, user.name)
                        usr['user']['tenantId'] = t.id
                        info['users'].append(usr)
                        break
        info['roles'] = [self.convert(role, self.config)
                         for role in self.get_roles_list()]
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

        def func():
            auth_ref = self._get_client_by_creds().auth_ref
            return keystone_client.Client(auth_ref=auth_ref,
                                          endpoint=self.config.cloud.auth_url,
                                          cacert=self.config.cloud.cacert,
                                          insecure=self.config.cloud.insecure)

        retrier = retrying.Retry(
            max_attempts=cfglib.CONF.migrate.retry,
            expected_exceptions=[ks_exceptions.Unauthorized],
            reraise_original_exception=True)
        return retrier.run(func)

    def _get_client_by_creds(self):
        """Authenticating with a user name and password.

        :return: OpenStack Keystone Client instance
        """

        return keystone_client.Client(
            username=self.config.cloud.user,
            password=self.config.cloud.password,
            tenant_name=self.config.cloud.tenant,
            auth_url=self.config.cloud.auth_url,
            cacert=self.config.cloud.cacert,
            insecure=self.config.cloud.insecure,
            region_name=self.config.cloud.region
        )

    def get_endpoint_by_service_type(self, service_type, endpoint_type):
        """Getting endpoint URL by service type.

        :param service_type: OpenStack service type (image, compute etc.)
        :param endpoint_type: publicURL or internalURL

        :return: String endpoint of specified OpenStack service
        """

        return self.keystone_client.service_catalog.url_for(
            service_type=service_type,
            endpoint_type=endpoint_type,
            region_name=self.config.cloud.region
        )

    def get_tenants_func(self, return_default_tenant=True):
        default_tenant = self.config.cloud.tenant \
            if return_default_tenant else NO_TENANT
        tenants = {tenant.id: tenant.name for tenant in
                   self.get_tenants_list()}

        def func(tenant_id):
            return tenants.get(tenant_id, default_tenant)

        return func

    def get_tenant_by_name(self, name):
        """Search tenant by name case-insensitively"""
        return find_by_name(
            'tenant', self.keystone_client.tenants.list(), name)

    def get_tenant_id_by_name(self, name):
        """ Getting tenant ID by name from keystone. """
        return self.get_tenant_by_name(name).id

    def try_get_tenant_by_id(self, tenant_id, default=None):
        """Returns `keystoneclient.tenants.Tenant` object based on tenant ID
        provided. If not found - returns :arg default: tenant. If
        :arg default: is not specified - returns `config.cloud.tenant`"""

        tenants = self.keystone_client.tenants
        try:
            with proxy_client.expect_exception(ks_exceptions.NotFound):
                return tenants.get(tenant_id)
        except ks_exceptions.NotFound:
            if default is None:
                return self.get_tenant_by_name(self.config.cloud.tenant)
            else:
                return tenants.get(default)

    def try_get_tenant_name_by_id(self, tenant_id, default=None):
        """ Same as `get_tenant_by_id` but returns `default` in case tenant
        ID is not present """
        try:
            with proxy_client.expect_exception(ks_exceptions.NotFound):
                return self.keystone_client.tenants.get(tenant_id).name
        except ks_exceptions.NotFound:
            LOG.warning("Tenant '%s' not found, returning default value = "
                        "'%s'", tenant_id, default)
            return default

    def get_services_list(self):
        """ Getting list of available services from keystone. """

        return self.keystone_client.services.list()

    def _get_required_tenants_list(self):
        """ Getting list of tenants, that are required for migration. """
        result = []
        filtering_enabled = (self.filter_tenant_id and
                             self.cloud.position == 'src')
        if filtering_enabled:
            result.append(
                self.keystone_client.tenants.find(id=self.filter_tenant_id))

            resources_with_public_objects = [
                self.cloud.resources[utl.IMAGE_RESOURCE],
                self.cloud.resources[utl.NETWORK_RESOURCE]
            ]

            tenants_required_by_resource = set()
            for r in resources_with_public_objects:
                for t in r.required_tenants(self.filter_tenant_id):
                    LOG.info('Tenant %s is required by %s', t,
                             r.__class__.__name__)
                    tenants_required_by_resource.add(t)
            tenant_ids = [self.filter_tenant_id]
            for tenant_id in tenants_required_by_resource:
                if tenant_id in tenant_ids:
                    continue

                tenant = self.try_get_tenant_by_id(tenant_id)

                # try_get_tenant_by_id may return config.cloud.tenant value
                if tenant.id not in tenant_ids:
                    tenant_ids.append(tenant.id)
                    result.append(tenant)
        else:
            result = self.get_tenants_list()
        LOG.info("List of tenants: %s", ", ".join('%s (%s)' % (t.name, t.id)
                                                  for t in result))
        return result

    def get_tenants_list(self):
        """ Getting list of all tenants from Keystone. """
        return self.keystone_client.tenants.list()

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
            with proxy_client.expect_exception(ks_exceptions.NotFound):
                return self.keystone_client.users.get(user_id).name
        except ks_exceptions.NotFound:
            return default

    def try_get_user_by_id(self, user_id, default=None):
        if default is None:
            admin_usr = self.try_get_user_by_name(self.config.cloud.user)
            default = admin_usr.id
        try:
            with proxy_client.expect_exception(ks_exceptions.NotFound):
                return self.keystone_client.users.find(id=user_id)
        except ks_exceptions.NotFound:
            LOG.warning("User '%s' has not been found, returning default "
                        "value = '%s'", user_id, default)
            return self.keystone_client.users.find(id=default)

    def try_get_user_by_name(self, username, default=None):
        return find_by_name(
            'user', self.keystone_client.users.list(), username, default)

    def get_default(self, resource_type):
        """ Get default of `resource_type` (Tenant or User).

        :return: object of `resource_type` type

        """
        if resource_type not in self.defaults:
            if resource_type == utl.TENANTS_TYPE:
                self.defaults[resource_type] = \
                    self.get_tenant_by_name(self.config.cloud.tenant)
            elif resource_type == utl.USERS_TYPE:
                self.defaults[resource_type] = \
                    self.try_get_user_by_name(self.config.cloud.user)
            else:
                raise NotImplementedError('Unknown resource type: %s',
                                          resource_type)
        return self.defaults[resource_type]

    def get_default_id(self, resource_type):
        """ Get default ID of `resource_type` (Tenant or User).

        :return: default ID

        """
        return self.get_default(resource_type).id

    def roles_for_user(self, user_id, tenant_id):
        """ Getting list of user roles for tenant """

        return self.keystone_client.roles.roles_for_user(user_id, tenant_id)

    def create_role(self, role_name):
        """ Create new role in keystone. """

        return self.keystone_client.roles.create(role_name)

    def delete_tenant(self, tenant):
        return self.keystone_client.tenants.delete(tenant)

    def create_tenant(self, tenant_name, description=None, enabled=True):
        """ Create new tenant in keystone. """

        try:
            with proxy_client.expect_exception(ks_exceptions.Conflict):
                return self.keystone_client.tenants.create(
                    tenant_name=tenant_name, description=description,
                    enabled=enabled)
        except ks_exceptions.Conflict:
            return self.get_tenant_by_name(tenant_name)

    def create_user(self, name, password=None, email=None, tenant_id=None,
                    enabled=True):
        """ Create new user in keystone. """

        try:
            with proxy_client.expect_exception(ks_exceptions.Conflict):
                return self.keystone_client.users.create(name=name,
                                                         password=password,
                                                         email=email,
                                                         tenant_id=tenant_id,
                                                         enabled=enabled)
        except ks_exceptions.Conflict:
            LOG.warning('Conflict creating user %s', name, exc_info=True)
            return self.try_get_user_by_name(name)

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
        LOG.info('Deploying tenants...')
        dst_tenants = {tenant.name.lower(): tenant.id for tenant in
                       self.get_tenants_list()}
        for _tenant in tenants:
            tenant = _tenant['tenant']
            if tenant['name'].lower() not in dst_tenants:
                LOG.debug("Creating tenant '%s'", tenant['name'])
                _tenant['meta']['new_id'] = self.create_tenant(
                    tenant['name'],
                    tenant['description']).id
            else:
                LOG.debug("Tenant '%s' is already present on destination, "
                          "skipping", tenant['name'])
                _tenant['meta']['new_id'] = dst_tenants[tenant['name'].lower()]

        LOG.info("Tenant deployment done.")

    def _deploy_users(self, users, tenants):
        dst_users = {user.name.lower(): user.id
                     for user in self.get_users_list()}
        tenant_mapped_ids = {tenant['tenant']['id']: tenant['meta']['new_id']
                             for tenant in tenants}

        keep_passwd = self.config['migrate']['keep_user_passwords']
        overwrite_passwd = self.config['migrate']['overwrite_user_passwords']

        for _user in users:
            user = _user['user']
            password = self._generate_password()

            if user['name'].lower() in dst_users:
                # Create users mapping
                _user['meta']['new_id'] = dst_users[user['name'].lower()]

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
        LOG.info("Role deployment started...")
        dst_roles = {
            role.name.lower(): role.id for role in self.get_roles_list()}
        for _role in roles:
            role = _role['role']
            if role['name'].lower() not in dst_roles:
                LOG.debug("Creating role '%s'", role['name'])
                _role['meta']['new_id'] = self.create_role(role['name']).id
            else:
                LOG.debug("Role '%s' is already present on destination, "
                          "skipping", role['name'])
                _role['meta']['new_id'] = dst_roles[role['name'].lower()]

        LOG.info("Role deployment done.")

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
        if not self.config.migrate.optimize_user_role_fetch:
            user_tenants_roles = \
                self._get_user_tenants_roles_by_api(tenant_list,
                                                    user_list)
        else:
            user_tenants_roles = \
                self._get_user_tenants_roles_by_db(tenant_list,
                                                   user_list)
        return user_tenants_roles

    def _get_roles_sql_request(self):
        res = []
        try:
            is_project_metadata = self.mysql_connector.execute(
                "SHOW TABLES LIKE 'user_project_metadata'").rowcount
            if is_project_metadata:  # for grizzly case
                return self.mysql_connector.execute(
                    "SELECT * FROM user_project_metadata")
            is_assignment = self.mysql_connector.execute(
                "SHOW TABLES LIKE 'assignment'").rowcount
            if is_assignment:  # for icehouse case
                res_raw = self.mysql_connector.execute(
                    "SELECT * FROM assignment")
                res_tmp = {}
                for (_, actor_id, project_id,
                     role_id, _) in res_raw:
                    if (actor_id, project_id) not in res_tmp:
                        res_tmp[(actor_id, project_id)] = {'roles': []}
                    res_tmp[(actor_id, project_id)]['roles'].append(role_id)
                for k, v in res_tmp.iteritems():
                    res.append((k[0], k[1], str(v)))
        except ProgrammingError as e:
            LOG.warn(e.message)
        return res

    def _get_user_roles_cached(self):
        all_roles = {}
        if self.config.migrate.optimize_user_role_fetch:
            LOG.debug('Fetching all roles for all tenants')
            res = self._get_roles_sql_request()
            for user_id, tenant_id, roles_field in res:
                roles_ids = ast.literal_eval(roles_field)['roles']
                user_roles = all_roles.setdefault(user_id, {})
                user_tenant_roles = user_roles.setdefault(tenant_id, [])
                user_tenant_roles.extend(roles_ids)
            LOG.debug('Done fetching all roles for all tenants')

        def _get_user_roles(user_id, tenant_id):
            if not self.config.migrate.optimize_user_role_fetch:
                roles = self.roles_for_user(user_id, tenant_id)
            else:
                roles = all_roles.get(user_id, {}).get(tenant_id, [])
            return roles
        return _get_user_roles

    def _get_user_tenants_roles_by_db(self, tenant_list, user_list):
        user_tenants_roles = {
            u.name.lower(): {t.name.lower(): [] for t in tenant_list}
            for u in user_list}
        tenant_ids = {tenant.id: tenant.name.lower() for tenant in tenant_list}
        user_ids = {user.id: user.name.lower() for user in user_list}
        roles = {r.id: r for r in self.get_roles_list()}
        for user_id, tenant_id, roles_field in self._get_roles_sql_request():
            # skip filtered tenants and users
            if user_id not in user_ids or tenant_id not in tenant_ids:
                continue

            roles_ids = ast.literal_eval(roles_field)['roles']
            db_version = self.get_db_version()
            if 29 <= db_version <= 38:
                _roles_ids = [role_id.get('id') for role_id in roles_ids]
            else:
                _roles_ids = roles_ids

            user_tenants_roles[user_ids[user_id]][tenant_ids[tenant_id]] = \
                [{'role': {'name': roles[r].name, 'id': r}}
                 for r in _roles_ids]
        return user_tenants_roles

    def _get_user_tenants_roles_by_api(self, tenant_list, user_list):
        user_tenants_roles = {}
        for user in user_list:
            user_tenants_roles[user.name.lower()] = {}
            for tenant in tenant_list:
                roles = []
                for role in self.roles_for_user(user.id, tenant.id):
                    roles.append({'role': {'name': role.name, 'id': role.id}})
                user_tenants_roles[user.name.lower()][tenant.name.lower()] = \
                    roles
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
        roles_id = {role.name.lower(): role.id
                    for role in self.get_roles_list()}
        dst_users = {user.name.lower(): user.id
                     for user in self.get_users_list()}
        dst_roles = {role.id: role.name.lower()
                     for role in self.get_roles_list()}
        get_user_roles = self._get_user_roles_cached()
        for _user in users:
            user = _user['user']
            if user['name'] not in dst_users:
                continue
            for _tenant in tenants:
                tenant = _tenant['tenant']
                user_roles_objs = get_user_roles(
                    _user['meta']['new_id'],
                    _tenant['meta']['new_id'])
                exists_roles = [dst_roles[role] if not hasattr(role, 'name')
                                else role.name.lower()
                                for role in user_roles_objs]
                user_roles = user_tenants_roles[user['name'].lower()]
                for _role in user_roles[tenant['name'].lower()]:
                    role = _role['role']
                    if role['name'].lower() in exists_roles:
                        continue
                    try:
                        with proxy_client.expect_exception(
                                ks_exceptions.Conflict):
                            self.keystone_client.roles.add_user_role(
                                _user['meta']['new_id'],
                                roles_id[role['name'].lower()],
                                _tenant['meta']['new_id'])
                    except ks_exceptions.Conflict:
                        LOG.info("Role '%s' for user '%s' in tenant '%s' "
                                 "already exists, skipping", role['name'],
                                 user['name'], tenant['name'])

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

    def get_db_version(self):
        res = self.mysql_connector.execute(
            "SELECT version FROM migrate_version"
        )
        for raw in res:
            return raw['version']

    @staticmethod
    def identical(src_tenant, dst_tenant):
        if not src_tenant:
            src_tenant = {'name': cfglib.CONF.src.tenant}
        if not dst_tenant:
            dst_tenant = {'name': cfglib.CONF.dst.tenant}
        return src_tenant['name'].lower() == dst_tenant['name'].lower()


def get_dst_tenant_from_src_tenant_id(src_keystone, dst_keystone,
                                      src_tenant_id):
    try:
        with proxy_client.expect_exception(ks_exceptions.NotFound):
            client = src_keystone.keystone_client
            src_tenant = client.tenants.find(id=src_tenant_id)
    except ks_exceptions.NotFound:
        return None

    try:
        with proxy_client.expect_exception(ks_exceptions.NotFound):
            client = dst_keystone.keystone_client
            return client.tenants.find(name=src_tenant.name)
    except ks_exceptions.NotFound:
        return None


def get_dst_user_from_src_user_id(src_keystone, dst_keystone, src_user_id,
                                  fallback_to_admin=True):
    """Returns user from destination with the same name as on source. None if
    user does not exist"""
    try:
        with proxy_client.expect_exception(ks_exceptions.NotFound):
            src_user = src_keystone.keystone_client.users.get(src_user_id)
        src_user_name = src_user.name
    except ks_exceptions.NotFound:
        LOG.warning("User '%s' not found on SRC!", src_user_id)
        if fallback_to_admin:
            LOG.warning("Replacing user '%s' with SRC admin", src_user_id)
            src_user_name = cfglib.CONF.src.user
        else:
            return

    if fallback_to_admin:
        default_user_name = cfglib.CONF.dst.user
    else:
        default_user_name = None
    try:
        with proxy_client.expect_exception(ks_exceptions.NotFound):
            return dst_keystone.try_get_user_by_name(
                src_user_name, default_user_name)
    except ks_exceptions.NotFound:
        return None


def find_by_name(object_name, objects, name, default=None):
    name_lower = name.lower()
    default_obj = None
    default_lower = default and default.lower()
    for obj in objects:
        obj_name = obj.name.lower()
        if obj_name == name_lower:
            return obj
        elif obj_name == default_lower:
            default_obj = obj
    LOG.warning('Object "%s" with name "%s" not found', object_name, name)
    if default_obj is not None:
        return default_obj
    else:
        if default is not None:
            LOG.warning('Could not find default "%s" with name "%s"',
                        object_name, default)
        raise ks_exceptions.NotFound(
            404, object_name + ' ' + name + ' not found!')
