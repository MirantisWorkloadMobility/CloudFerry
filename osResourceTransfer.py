"""
Package with OpenStack resources export/import utilities.
"""
import osCommon
from utils import log_step, get_log, GeneratorPassword, Postman, Templater
import sqlalchemy

LOG = get_log(__name__)


class ResourceExporter(osCommon.osCommon):
    """
    Exports various cloud resources (tenants, users, flavors, etc.) to a container
    to be later imported by ResourceImporter
    """

    def __init__(self, conf):
        self.data = dict()
        self.config = conf['clouds']['from']
        super(ResourceExporter, self).__init__(self.config)

    @log_step(2, LOG)
    def get_flavors(self):
        def process_flavor(flavor):
            if flavor.is_public:
                return (flavor, [])
            else:
                tenants = self.nova_client.flavor_access.list(flavor=flavor)
                tenants = [self.keystone_client.tenants.get(t.tenant_id).name for t in tenants]
                return (flavor, tenants)

        self.data['flavors'] = map(process_flavor, self.nova_client.flavors.list(is_public=False))
        return self

    @log_step(2, LOG)
    def get_tenants(self):
        self.data['tenants'] = self.keystone_client.tenants.list()
        return self

    @log_step(2, LOG)
    def get_roles(self):
        self.data['roles'] = self.keystone_client.roles.list()
        return self

    @log_step(2, LOG)
    def get_user_info(self):
        self.__get_user_info(self.config['keep_user_passwords'])
        return self

    def __get_user_info(self, with_password):
        users = self.keystone_client.users.list()
        info = {}
        if with_password:
            with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
                for user in users:
                    for password in connection.execute(sqlalchemy.text("SELECT password FROM user WHERE id = :user_id"),
                                                       user_id=user.id):
                        info[user.name] = password[0]
        self.data['users'] = info

    @log_step(2, LOG)
    def build(self):
        return self.data


class ResourceImporter(osCommon.osCommon):
    """
    Imports various cloud resources (tenants, users, flavors, etc.) from a container
    prepared by ResourceExporter
    """

    def __init__(self, conf):
        self.config = conf['clouds']['to']
        if 'mail' in conf:
            self.postman = Postman(**conf['mail'])
        else:
            self.postman = None
        self.templater = Templater()
        self.generator = GeneratorPassword()
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

    @log_step(2, LOG)
    def upload(self, data):
        self.__upload_roles(data['roles'])
        self.__upload_tenants(data['tenants'])
        self.__upload_flavors(data['flavors'])
        if data['users']:
            self.__upload_user_passwords(data['users'])
        else:
            self.__send_email_notifications()

    @log_step(3, LOG)
    def __upload_roles(self, roles):
        # do not import a role if one with the same name already exists
        existing = {r.name for r in self.keystone_client.roles.list()}
        for role in roles:
            if role.name not in existing:
                self.keystone_client.roles.create(role.name)

    @log_step(3, LOG)
    def __upload_tenants(self, tenants):
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

    @log_step(3, LOG)
    def __upload_flavors(self, flavors):
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


    @log_step(3, LOG)
    def __upload_user_passwords(self, users):
        # upload user password if the user exists both on source and destination
        with sqlalchemy.create_engine(self.keystone_db_conn_url).begin() as connection:
            for user in self.keystone_client.users.list():
                if user.name in users:
                    connection.execute(sqlalchemy.text("UPDATE user SET password = :password WHERE id = :user_id"),
                                       user_id=user.id,
                                       password=users[user.name])

    def __send_email_notifications(self):
        for name in self.users_notifications:
            self.__send_msg(self.users_notifications[name]['email'],
                            'New password notification',
                            self.__render_template('email.html',
                                                   {'name': name,
                                                    'password': self.users_notifications[name]['password']}))
