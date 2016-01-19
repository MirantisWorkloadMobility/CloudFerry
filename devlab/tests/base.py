# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from glanceclient.v1 import Client as glance
from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v2_0 import client as keystone

from novaclient.v1_1 import client as nova
from neutronclient.v2_0 import client as neutron
from cinderclient.v1 import client as cinder

from test_exceptions import NotFound
import utils

OPENSTACK_RELEASES = {'192.168.1.2': 'grizzly',
                      '192.168.1.3': 'icehouse',
                      '192.168.1.8': 'juno'}


class BasePrerequisites(object):

    def __init__(self, config, configuration_ini, cloud_prefix='SRC'):
        self.configuration_ini = configuration_ini
        self.filtering_utils = utils.FilteringUtils(
            self.configuration_ini['migrate']['filter_path'])
        self.migration_utils = utils.MigrationUtils(config)

        self.config = config
        self.cloud_prefix = cloud_prefix.lower()

        self.username = self.configuration_ini[self.cloud_prefix]['user']
        self.password = self.configuration_ini[self.cloud_prefix]['password']
        self.tenant = self.configuration_ini[self.cloud_prefix]['tenant']
        self.auth_url = self.configuration_ini[self.cloud_prefix]['auth_url']

        self.keystoneclient = keystone.Client(auth_url=self.auth_url,
                                              username=self.username,
                                              password=self.password,
                                              tenant_name=self.tenant)
        self.keystoneclient.authenticate()

        self.novaclient = nova.Client(username=self.username,
                                      api_key=self.password,
                                      project_id=self.tenant,
                                      auth_url=self.auth_url)

        self.token = self.keystoneclient.auth_token

        self.image_endpoint = \
            self.keystoneclient.service_catalog.get_endpoints(
                service_type='image',
                endpoint_type='publicURL')['image'][0]['publicURL']

        self.glanceclient = glance(endpoint=self.image_endpoint,
                                   token=self.token)

        self.neutronclient = neutron.Client(username=self.username,
                                            password=self.password,
                                            tenant_name=self.tenant,
                                            auth_url=self.auth_url)

        self.cinderclient = cinder.Client(self.username, self.password,
                                          self.tenant, self.auth_url)
        self.openstack_release = self._get_openstack_release()
        self.server_groups_supported = self.openstack_release in ['icehouse',
                                                                  'juno']

    def _get_openstack_release(self):
        for release in OPENSTACK_RELEASES:
            if release in self.auth_url:
                return OPENSTACK_RELEASES[release]
        raise RuntimeError('Unknown OpenStack release')

    def get_vagrant_vm_ip(self):
        for release in OPENSTACK_RELEASES:
            if release in self.auth_url:
                return release

    def get_tenant_id(self, tenant_name):
        for tenant in self.keystoneclient.tenants.list():
            if tenant.name == tenant_name:
                return tenant.id
        raise NotFound('Tenant with name "%s" was not found' % tenant_name)

    def get_tenant_name(self, tenant_id):
        for tenant in self.keystoneclient.tenants.list():
            if tenant.id == tenant_id:
                return tenant.name
        raise NotFound('Tenant with id "%s" was not found' % tenant_id)

    def get_user_id(self, user_name):
        for user in self.keystoneclient.users.list():
            if user.name == user_name:
                return user.id
        raise NotFound('User with name "%s" was not found' % user_name)

    def get_router_id(self, router):
        _router = self.neutronclient.list_routers(name=router)['routers']
        if _router:
            return _router[0]['id']
        raise NotFound('Router with name "%s" was not found' % router)

    def get_image_id(self, image_name):
        for image in self.glanceclient.images.list():
            if image.name == image_name:
                return image.id
        raise NotFound('Image with name "%s" was not found' % image_name)

    def get_flavor_id(self, flavor_name):
        for flavor in self.novaclient.flavors.list():
            if flavor.name == flavor_name:
                return flavor.id
        raise NotFound('Flavor with name "%s" was not found' % flavor_name)

    def get_vm_id(self, vm_name):
        for vm in self.novaclient.servers.list(search_opts={'all_tenants': 1}):
            if vm.name == vm_name:
                return vm.id
        raise NotFound('VM with name "%s" was not found' % vm_name)

    def get_role_id(self, role_name):
        for role in self.keystoneclient.roles.list():
            if role.name == role_name:
                return role.id
        raise NotFound('Role with name "%s" was not found' % role_name)

    def get_net_id(self, net):
        _net = self.neutronclient.list_networks(
            name=net, all_tenants=True)['networks']
        if _net:
            return _net[0]['id']
        raise NotFound('Network with name "%s" was not found' % net)

    def get_net_name(self, net_id):
        _net = self.neutronclient.list_networks(id=net_id,
                                                all_tenants=True)['networks']
        if _net:
            return _net[0]['name']
        raise NotFound('Network with id "%s" was not found' % net_id)

    def get_sg_id(self, sg):
        _sg = self.neutronclient.list_security_groups(
            name=sg, all_tenants=True)['security_groups']
        if _sg:
            return _sg[0]['id']
        raise NotFound('Security group with name "%s" was not found' % sg)

    def get_server_group_id(self, server_group_name):
        for server_group in self.get_all_server_groups():
            if server_group.name == server_group_name:
                return server_group.id
        msg = 'Server group with name "%s" was not found'
        raise NotFound(msg % server_group_name)

    def get_volume_id(self, volume_name):
        volumes = self.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        for volume in volumes:
            if volume.display_name == volume_name:
                return volume.id
        raise NotFound('Volume with name "%s" was not found' % volume_name)

    def get_volume_snapshot_id(self, snapshot_name):
        snapshots = self.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})
        for snapshot in snapshots:
            if snapshot.display_name == snapshot_name:
                return snapshot.id
        raise NotFound('Snapshot with name "%s" was not found' % snapshot_name)

    def get_user_tenant_roles(self, user):
        user_tenant_roles = []
        for tenant in self.keystoneclient.tenants.list():
            user_tenant_roles.extend(self.keystoneclient.roles.roles_for_user(
                user=self.get_user_id(user.name),
                tenant=self.get_tenant_id(tenant.name)))
        return user_tenant_roles

    def get_ext_routers(self):
        routers = self.neutronclient.list_routers()['routers']
        ext_routers = [router for router in routers
                       if router['external_gateway_info']]
        return ext_routers

    def get_sec_group_id_by_tenant_id(self, tenant_id):
        sec_group_list = self.neutronclient.list_security_groups()
        return [i['id'] for i in sec_group_list['security_groups']
                if i['tenant_id'] == tenant_id]

    def get_users_keypairs(self):
        self.switch_user(self.username, self.password, self.tenant)
        user_names = [u['name'] for u in self.config.users]
        keypairs = []
        for user in self.config.users:
            if user['name'] not in user_names:
                continue
            if not user.get('enabled') or user.get('deleted'):
                continue
            if not self.tenant_exists(user['tenant']) or \
                    not self.user_has_not_primary_tenants(user['name']):
                continue
            try:
                self.switch_user(user['name'], user['password'],
                                 user['tenant'])
            except ks_exceptions.Unauthorized:
                self.keystoneclient.users.update(
                    self.get_user_id(user['name']), password=user['password'],
                    tenant=user['tenant'])
                self.switch_user(user['name'], user['password'],
                                 user['tenant'])
            keypairs.extend(self.novaclient.keypairs.list())
        return keypairs

    def get_all_server_groups(self):
        initial_tenant = self.keystoneclient.tenant_name
        self.switch_user(self.username, self.password, self.tenant)
        server_groups = self.novaclient.server_groups.list()
        for tenant in self.config.tenants:
            if not self.tenant_exists(tenant['name']):
                continue
            with utils.AddAdminUserRoleToNonAdminTenant(
                    self.keystoneclient, self.username, tenant['name']):
                self.switch_user(self.username, self.password,
                                 tenant['name'])
                server_groups.extend(self.novaclient.server_groups.list())
        self.switch_user(self.username, self.password, initial_tenant)
        return server_groups

    def user_has_not_primary_tenants(self, user_name):
        user_id = self.get_user_id(user_name)
        for tenant in self.keystoneclient.tenants.list():
            if self.keystoneclient.roles.roles_for_user(user=user_id,
                                                        tenant=tenant.id):
                return True
        return False

    def check_vm_state(self, srv):
        srv = self.novaclient.servers.get(srv)
        return srv.status == 'ACTIVE'

    def tenant_exists(self, tenant_name=None, tenant_id=None):
        self.switch_user(self.username, self.password, self.tenant)
        try:
            if tenant_name is not None:
                self.keystoneclient.tenants.find(name=tenant_name)
            else:
                self.keystoneclient.tenants.find(id=tenant_id)
        except ks_exceptions.NotFound:
            return False
        else:
            return True

    def switch_user(self, user, password, tenant):
        self.keystoneclient = keystone.Client(auth_url=self.auth_url,
                                              username=user,
                                              password=password,
                                              tenant_name=tenant)
        self.keystoneclient.authenticate()
        self.token = self.keystoneclient.auth_token
        self.novaclient = nova.Client(username=user,
                                      api_key=password,
                                      project_id=tenant,
                                      auth_url=self.auth_url)

        self.glanceclient = glance(endpoint=self.image_endpoint,
                                   token=self.token)

        self.neutronclient = neutron.Client(username=user,
                                            password=password,
                                            tenant_name=tenant,
                                            auth_url=self.auth_url)

        self.cinderclient = cinder.Client(user, password, tenant,
                                          self.auth_url)
