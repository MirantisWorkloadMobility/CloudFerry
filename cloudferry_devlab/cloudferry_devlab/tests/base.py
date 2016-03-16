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

import contextlib
import logging
import os
import time

from cinderclient.v1 import client as cinder
from glanceclient.v1 import Client as glance
from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v2_0 import client as keystone
from neutronclient.v2_0 import client as neutron
from novaclient import exceptions as nova_exceptions
from novaclient.v1_1 import client as nova
from swiftclient import client as swift_client

from cloudferry_devlab.tests import test_exceptions
import cloudferry_devlab.tests.utils as utils

LOG = logging.getLogger(__name__)
OPENSTACK_RELEASES = {'192.168.1.2': 'grizzly',
                      '192.168.1.3': 'icehouse',
                      '192.168.1.8': 'juno'}
SWIFT_AUTH_VERSION = '2'


class SwiftConnection(object):
    def __init__(self, auth_url, username, password, tenant):
        self.auth_url = auth_url
        self.username = username
        self.password = password
        self.tenant = tenant

    @contextlib.contextmanager
    def __call__(self):
        conn = swift_client.Connection(
            authurl=self.auth_url,
            user=self.username,
            key=self.password,
            tenant_name=self.tenant,
            auth_version=SWIFT_AUTH_VERSION)
        try:
            yield conn
        finally:
            conn.close()


class BasePrerequisites(object):

    def __init__(self, config, configuration_ini, cloud_prefix='SRC',
                 results_path='.'):
        self.configuration_ini = configuration_ini
        self.results_path = results_path
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
        self.swift_connection = SwiftConnection(self.auth_url, self.username,
                                                self.password, self.tenant)

    def put_swift_container(self, container_name):
        """Create a container."""

        with self.swift_connection() as swift_conn:
            swift_conn.put_container(container_name)

    def delete_swift_container(self, container_name):
        """Delete a container"""

        with self.swift_connection() as swift_conn:
            swift_conn.delete_container(container_name)

    def put_swift_object(self, container_name, obj_name, contents=None):
        """Create an object."""

        with self.swift_connection() as swift_conn:
            swift_conn.put_object(container_name, obj_name, contents)

    def post_swift_object(self, container_name, obj_name, metadata):
        """Update object metadata."""

        with self.swift_connection() as swift_conn:
            swift_conn.post_object(container_name, obj_name, metadata)

    def delete_swift_object(self, container_name, obj_name):
        """Delete an object"""

        with self.swift_connection() as swift_conn:
            swift_conn.delete_object(container_name, obj_name)

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
        raise test_exceptions.NotFound('Tenant with name "%s" was not found'
                                       % tenant_name)

    def get_tenant_name(self, tenant_id):
        for tenant in self.keystoneclient.tenants.list():
            if tenant.id == tenant_id:
                return tenant.name
        raise test_exceptions.NotFound('Tenant with id "%s" was not found'
                                       % tenant_id)

    def get_user_id(self, user_name):
        for user in self.keystoneclient.users.list():
            if user.name == user_name:
                return user.id
        raise test_exceptions.NotFound('User with name "%s" was not found'
                                       % user_name)

    def get_router_id(self, router):
        _router = self.neutronclient.list_routers(name=router)['routers']
        if _router:
            return _router[0]['id']
        raise test_exceptions.NotFound('Router with name "%s" was not found'
                                       % router)

    def get_image_id(self, image_name):
        for image in self.glanceclient.images.list():
            if image.name == image_name:
                return image.id
        raise test_exceptions.NotFound('Image with name "%s" was not found'
                                       % image_name)

    def get_flavor_id(self, flavor_name):
        for flavor in self.novaclient.flavors.list():
            if flavor.name == flavor_name:
                return flavor.id
        raise test_exceptions.NotFound('Flavor with name "%s" was not found'
                                       % flavor_name)

    def get_vm_id(self, vm_name):
        for vm in self.novaclient.servers.list(search_opts={'all_tenants': 1}):
            if vm.name == vm_name:
                return vm.id
        raise test_exceptions.NotFound('VM with name "%s" was not found'
                                       % vm_name)

    def get_role_id(self, role_name):
        for role in self.keystoneclient.roles.list():
            if role.name == role_name:
                return role.id
        raise test_exceptions.NotFound('Role with name "%s" was not found'
                                       % role_name)

    def get_net_id(self, net):
        _net = self.neutronclient.list_networks(
            name=net, all_tenants=True)['networks']
        if _net:
            return _net[0]['id']
        raise test_exceptions.NotFound('Network with name "%s" was not found'
                                       % net)

    def get_net_name(self, net_id):
        _net = self.neutronclient.list_networks(id=net_id,
                                                all_tenants=True)['networks']
        if _net:
            return _net[0]['name']
        raise test_exceptions.NotFound('Network with id "%s" was not found'
                                       % net_id)

    def get_sg_id(self, sg):
        _sg = self.neutronclient.list_security_groups(
            name=sg, all_tenants=True)['security_groups']
        if _sg:
            return _sg[0]['id']
        raise test_exceptions.NotFound('Security group with name "%s" was not'
                                       ' found' % sg)

    def get_server_group_id(self, server_group_name):
        for server_group in self.get_all_server_groups():
            if server_group.name == server_group_name:
                return server_group.id
        msg = 'Server group with name "%s" was not found'
        raise test_exceptions.NotFound(msg % server_group_name)

    def get_volume_id(self, volume_name):
        volumes = self.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        for volume in volumes:
            if volume.display_name == volume_name:
                return volume.id
        raise test_exceptions.NotFound('Volume with name "%s" was not found'
                                       % volume_name)

    def get_volume_snapshot_id(self, snapshot_name):
        snapshots = self.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})
        for snapshot in snapshots:
            if snapshot.display_name == snapshot_name:
                return snapshot.id
        raise test_exceptions.NotFound('Snapshot with name "%s" was not found'
                                       % snapshot_name)

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

    def check_vm_state(self, srv_id):
        srv = self.novaclient.servers.get(srv_id)
        if srv.status == 'ERROR':
            msg = 'VM with id {0} was spawned in error state'
            raise RuntimeError(msg.format(srv_id))
        return srv.status == 'ACTIVE'

    def check_image_state(self, img_id):
        img = self.glanceclient.images.get(img_id)
        return img.status == 'active'

    def check_volume_state(self, vol_id):
        vlm = self.cinderclient.volumes.get(vol_id)
        if vlm.status == 'available' or vlm.status == 'in-use':
            return True
        elif vlm.status == 'error':
            msg = 'Volume with id {0} was created with error'
            raise RuntimeError(msg.format(vol_id))
        return False

    def check_snapshot_state(self, snp_id):
        snp = self.glanceclient.images.get(snp_id)
        if snp.status == 'active':
            return True
        elif snp.status == 'error':
            msg = 'Snapshot with id {0} has become in error state'
            raise RuntimeError(msg.format(snp_id))
        return False

    @staticmethod
    def check_floating_ip_assigned(vm, floating_ip_address):
        for net in vm.addresses:
            for addr in vm.addresses.get(net):
                if addr.get('OS-EXT-IPS:type') == 'floating':
                    return True
        try:
            vm.add_floating_ip(floating_ip_address)
        except nova_exceptions.BadRequest as e:
            LOG.warning("Floating IP is already assigned to VM: %s", e)
        return False

    @staticmethod
    def wait_until_objects_created(obj_list, check_func, timeout):
        obj_list = obj_list[:]
        waiting = 0
        delay = 1
        while waiting < timeout:
            for obj in obj_list[:]:
                args = obj if isinstance(obj, tuple) else (obj, )
                if check_func(*args):
                    obj_list.remove(obj)
            if not obj_list:
                return
            time.sleep(delay)
            waiting += delay
            delay *= 2
        msg = 'Objects {0} has not become in active state after timeout.'
        raise RuntimeError(msg.format(obj_list))

    def tenant_exists(self, tenant_name=None, tenant_id=None):
        self.switch_user(self.username, self.password, self.tenant)
        try:
            if tenant_name is not None:
                self.keystoneclient.tenants.find(name=tenant_name)
            else:
                self.keystoneclient.tenants.find(id=tenant_id)
        except ks_exceptions.NotFound:
            return False
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

    def get_abs_path(self, file_path):
        return os.path.join(os.path.dirname(self.results_path), file_path)


def get_dict_from_config_file(config_file):
    conf_dict = {}
    for section in config_file.sections():
        conf_dict[section] = {}
        for option in config_file.options(section):
            conf_dict[section][option] = config_file.get(section, option)
    return conf_dict
