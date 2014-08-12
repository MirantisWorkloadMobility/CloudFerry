"""
Package with OpenStack resources export/import utilities.
"""
from migrationlib.os import osCommon
from utils import log_step, get_log, GeneratorPassword, Postman, Templater
from scheduler.builder_wrapper import inspect_func, supertask
import sqlalchemy

LOG = get_log(__name__)


class ResourceImporter(osCommon.osCommon):
    """
    Imports various cloud resources (tenants, users, flavors, etc.) from a container
    prepared by ResourceExporter
    """

    def __init__(self, conf, data={}, users_notifications={}):
        self.config = conf['clouds']['to']
        if 'mail' in conf:
            self.postman = Postman(**conf['mail'])
        else:
            self.postman = None
        self.templater = Templater()
        self.generator = GeneratorPassword()
        self.users_notifications = users_notifications
        self.data = data
        self.funcs = []
        super(ResourceImporter, self).__init__(self.config)

    def __send_msg(self, to, subject, msg):
        if self.postman:
            with self.postman as p:
                p.send(to, subject, msg)

    def __render_template(self, name_file, args):
        if self.templater:
            return self.templater.render(name_file, args)
        else:
            return None

    def __generate_password(self):
        if self.generator:
            return self.generator.get_random_password()
        else:
            return None

    def get_tasks(self):
        return self.funcs

    def get_state(self):
        return {
            'users_notifications': self.users_notifications,
        }

    def finish(self):
        for f in self.funcs:
            f()
        self.funcs = []
        LOG.info("| Resource migrated")

    @inspect_func
    @supertask
    def upload(self, data=None, **kwargs):
        self.data = data if data else self.data
        self\
            .upload_roles()\
            .upload_tenants()\
            .upload_flavors()\
            .upload_user_passwords()\
            .send_email_notifications()
        return self

    @inspect_func
    @log_step(LOG)
    def upload_roles(self, data=None, **kwargs):
        roles = data['roles'] if data else self.data['roles']
        # do not import a role if one with the same name already exists
        existing = {r.name for r in self.keystone_client.roles.list()}
        for role in roles:
            if role.name not in existing:
                self.keystone_client.roles.create(role.name)
        return self

    @inspect_func
    @log_step(LOG)
    def upload_tenants(self, data=None, **kwargs):
        tenants = data['tenants'] if data else self.data['tenants']
        # do not import tenants or users if ones with the same name already exist
        existing_tenants = {t.name: t for t in self.keystone_client.tenants.list()}
        existing_users = {u.name: u for u in self.keystone_client.users.list()}
        # by this time roles on source and destination should be synchronized
        roles = {r.name: r for r in self.keystone_client.roles.list()}
        self.users_notifications = {}
        for tenant in tenants:
            if tenant.name not in existing_tenants:
                dest_tenant = self.keystone_client.tenants.create(tenant_name=tenant.name,
                                                                  description=tenant.description,
                                                                  enabled=tenant.enabled)
            else:
                dest_tenant = existing_tenants[tenant.name]
            # import users of this tenant that don't exist yet
            for user in tenant.list_users():
                if user.name not in existing_users:
                    new_password = self.__generate_password()
                    dest_user = self.keystone_client.users.create(name=user.name,
                                                                  password=new_password,
                                                                  email=user.email,
                                                                  tenant_id=dest_tenant.id,
                                                                  enabled=user.enabled)
                    self.users_notifications[user.name] = {
                        'email': user.email,
                        'password': new_password
                    }
                else:
                    dest_user = existing_users[user.name]
                # import roles of this user within the tenant that are not already assigned
                dest_user_roles = {r.name for r in dest_user.list_roles(dest_tenant)}
                for role in user.list_roles(tenant):
                    if role.name not in dest_user_roles:
                        dest_tenant.add_user(dest_user, roles[role.name])
        return self

    @inspect_func
    @log_step(LOG)
    def upload_flavors(self, data=None, **kwargs):
        flavors = data['flavors'] if data else self.data['flavors']
        # do not import a flavor if one with the same name already exists
        existing = {f.name for f in self.nova_client.flavors.list(is_public=False)}
        for (flavor, tenants) in flavors:
            if flavor.name not in existing:
                dest_flavor = self.nova_client.flavors.create(name=flavor.name,
                                                              ram=flavor.ram,
                                                              vcpus=flavor.vcpus,
                                                              disk=flavor.disk,
                                                              swap=flavor.swap,
                                                              rxtx_factor=flavor.rxtx_factor,
                                                              ephemeral=flavor.ephemeral,
                                                              is_public=flavor.is_public)
                for tenant in tenants:
                    dest_tenant = self.keystone_client.tenants.find(name=tenant)
                    self.nova_client.flavor_access.add_tenant_access(dest_flavor, dest_tenant.id)
        return self

    @inspect_func
    @log_step(LOG)
    def upload_user_passwords(self, data=None, **kwargs):
        users = data['users'] if data else self.data['users']
        # upload user password if the user exists both on source and destination
        if users:
            with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
                for user in self.keystone_client.users.list():
                    if user.name in users:
                        connection.execute(sqlalchemy.text("UPDATE user SET password = :password WHERE id = :user_id"),
                                           user_id=user.id,
                                           password=users[user.name])
        return self

    @inspect_func
    @log_step(LOG)
    def send_email_notifications(self, users_notifications=None, template='templates/email.html', **kwargs):
        users_notifications = users_notifications if users_notifications else self.users_notifications
        for name in users_notifications:
            self.__send_msg(users_notifications[name]['email'],
                            'New password notification',
                            self.__render_template(template,
                                                   {'name': name,
                                                    'password': users_notifications[name]['password']}))
        return self