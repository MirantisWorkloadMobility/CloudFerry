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

import itertools
import logging
import time
from logging import config as logging_config

from keystoneclient import exceptions as ks_exceptions
from neutronclient.common import exceptions as nt_exceptions
from novaclient import exceptions as nv_exceptions

from cloudferry_devlab.tests import base
import cloudferry_devlab.tests.config as conf
from cloudferry_devlab.tests import test_exceptions

logging_config.dictConfig(conf.logging_configuration)
LOG = logging.getLogger(__name__)


class CleanEnv(base.BasePrerequisites):

    def clean_vms(self):
        vms = self.migration_utils.get_all_vms_from_config()
        vms_names = [vm['name'] for vm in vms]
        vms = self.novaclient.servers.list(search_opts={'all_tenants': 1})
        vms_ids = []
        for vm in vms:
            if vm.name not in vms_names:
                continue
            vms_ids.append(vm.id)
            self.novaclient.servers.delete(vm.id)
            LOG.info('VM "%s" has been deleted',  vm.name)
        self.wait_vms_deleted()

    def wait_vms_deleted(self, tenant_id=None):
        search_opts = {'all_tenants': 1}
        if tenant_id is not None:
            search_opts['tenant_id'] = tenant_id
        timeout = 120
        for _ in range(timeout):
            servers = self.novaclient.servers.list(
                search_opts=search_opts)
            if not servers:
                break
            for server in servers:
                if server.status != 'DELETED':
                    time.sleep(1)
                try:
                    self.novaclient.servers.delete(server.id)
                except nv_exceptions.NotFound:
                    pass
        else:
            raise RuntimeError('Next vms were not deleted')

    def clean_volumes(self):
        volumes = self.config.cinder_volumes
        volumes += itertools.chain(*[tenant['cinder_volumes'] for tenant
                                     in self.config.tenants if 'cinder_volumes'
                                     in tenant])
        for volume in self.config.cinder_volumes_from_images:
            volumes.append(volume)
        volumes_names = [volume['display_name'] for volume in volumes]
        volumes = self.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        for volume in volumes:
            if volume.display_name not in volumes_names:
                continue
            self.cinderclient.volumes.delete(
                self.get_volume_id(volume.display_name))
            LOG.info('Volume "%s" has been deleted', volume.display_name)

    def clean_swift_containers_and_objects(self):
        containers = self.config.swift_containers
        for container in containers:
            for obj in container.get('objects', []):
                self.delete_swift_object(container['name'], obj['name'])
            self.delete_swift_container(container['name'])

    def clean_flavors(self):
        flavors_names = [flavor['name'] for flavor in self.config.flavors]
        for tenant in self.config.tenants:
            if not tenant.get('flavors'):
                continue
            flavors_names.extend([f['name'] for f in tenant['flavors']])
        for flavor in self.novaclient.flavors.list(is_public=None):
            if flavor.name not in flavors_names:
                continue
            self.novaclient.flavors.delete(self.get_flavor_id(flavor.name))
            LOG.info('Flavor "%s" has been deleted', flavor.name)

    def clean_images(self):
        all_images = self.migration_utils.get_all_images_from_config()
        images_names = [image['name'] for image in all_images]

        for image in self.glanceclient.images.list():
            if image.name not in images_names:
                continue
            self.glanceclient.images.delete(self.get_image_id(image.name))
            LOG.info('Image "%s" has been deleted', image.name)

    def clean_snapshots(self):
        snaps_names = [snapshot['image_name']
                       for snapshot in self.config.snapshots]
        for snapshot in self.glanceclient.images.list():
            if snapshot.name not in snaps_names:
                continue
            self.glanceclient.images.delete(
                self.get_image_id(snapshot.name))
            LOG.info('Snapshot "%s" has been deleted', snapshot.name)

    def clean_networks(self):
        nets = self.config.networks
        nets += itertools.chain(*[tenant['networks'] for tenant
                                  in self.config.tenants
                                  if tenant.get('networks')])
        nets_names = [net['name'] for net in nets]
        for network in self.neutronclient.list_networks()['networks']:
            if network['name'] not in nets_names:
                continue
            net_id = self.get_net_id(network['name'])
            self.clean_network_ports(net_id)
            self.neutronclient.delete_network(net_id)
            LOG.info('Network "%s" has been deleted', network['name'])

    def delete_port(self, port):
        port_owner = port['device_owner']
        if port_owner == 'network:router_gateway':
            self.neutronclient.remove_gateway_router(port['device_id'])
        elif port_owner == 'network:router_interface':
            self.neutronclient.remove_interface_router(
                port['device_id'], {'port_id': port['id']})
        elif port_owner == 'network:dhcp' or not port_owner:
            self.neutronclient.delete_port(port['id'])
        elif 'LOADBALANCER' in port_owner:
            vips = self.neutronclient.list_vips(port_id=port['id'])['vips']
            for vip in vips:
                self.neutronclient.delete_vip(vip['id'])
        else:
            msg = 'Unknown port owner %s'
            raise RuntimeError(msg % port['device_owner'])

    def clean_network_ports(self, net_id):
        ports = self.neutronclient.list_ports(network_id=net_id)['ports']
        for port in ports:
            self.delete_port(port)

    def clean_router_ports(self, router_id):
        ports = self.neutronclient.list_ports(device_id=router_id)['ports']
        for port in ports:
            self.delete_port(port)

    def clean_routers(self):
        router_names = [router['router']['name']
                        for router in self.config.routers]
        for tenant in self.config.tenants:
            if tenant.get('routers'):
                for router in tenant['routers']:
                    router_names.append(router['router']['name'])
        for router in self.neutronclient.list_routers()['routers']:
            if router['name'] not in router_names:
                continue
            router_id = self.get_router_id(router['name'])
            self.clean_router_ports(router_id)
            self.neutronclient.delete_router(router_id)
            LOG.info('Router "%s" has been deleted', router['name'])

    def clean_fips(self):
        floatingips = self.neutronclient.list_floatingips()['floatingips']
        for ip in floatingips:
            try:
                self.neutronclient.delete_floatingip(ip['id'])
            except nt_exceptions.NeutronClientException:
                LOG.warning("Ip %s failed to delete:",
                            ip['floating_ip_address'], exc_info=True)

    def clean_security_groups(self):
        sgs = self.neutronclient.list_security_groups()['security_groups']
        for sg in sgs:
            try:
                self.neutronclient.delete_security_group(self.get_sg_id(
                    sg['name']))
            except (nt_exceptions.NeutronClientException,
                    test_exceptions.NotFound):
                LOG.warning("Security group %s failed to delete:",
                            sg['name'], exc_info=True)

    def clean_roles(self):
        roles_names = [role['name'] for role in self.config.roles]
        for role in self.keystoneclient.roles.list():
            if role.name not in roles_names:
                continue
            self.keystoneclient.roles.delete(self.get_role_id(role.name))
            LOG.info('Role "%s" has been deleted', role.name)

    def clean_keypairs(self):
        def delete_user_keypairs(_user):
            if not _user.get('enabled'):
                return
            try:
                self.switch_user(user=_user['name'], tenant=_user['tenant'],
                                 password=_user['password'])
            except ks_exceptions.Unauthorized:
                return

            keypairs = [k.id for k in self.novaclient.keypairs.list()]
            if keypairs:
                for key_pair in keypairs:
                    self.novaclient.keypairs.delete(key_pair)
            self.switch_user(user=self.username, password=self.password,
                             tenant=self.tenant)

        for user in self.config.users:
            delete_user_keypairs(user)

    def clean_users(self):
        users_names = [user['name'] for user in self.config.users]
        for user in self.keystoneclient.users.list():
            if user.name not in users_names:
                continue
            self.keystoneclient.users.delete(self.get_user_id(user.name))
            LOG.info('User "%s" has been deleted', user.name)

    def clean_tenants(self):
        tenants_names = [tenant['name'] for tenant in self.config.tenants]
        for tenant in self.keystoneclient.tenants.list():
            if tenant.name not in tenants_names:
                continue
            self.keystoneclient.tenants.delete(self.get_tenant_id(tenant.name))
            LOG.info('Tenant "%s" has been deleted', tenant.name)

    def clean_cinder_snapshots(self):
        snapshots = self.config.cinder_snapshots
        snapshots += itertools.chain(
            *[tenant['cinder_snapshots'] for tenant in self.config.tenants
              if 'cinder_snapshots' in tenant])
        sn_names = [snapshot['name'] for snapshot in snapshots]
        snapshots = self.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})
        for snapshot in snapshots:
            if snapshot.name not in sn_names:
                continue
            self.cinderclient.volume_snapshots.delete(
                self.get_volume_snapshot_id(snapshot.display_name))
            LOG.info('Snapshot "%s" has been deleted', snapshot.display_name)

    def clean_namespaces(self):
        ip_addr = self.get_vagrant_vm_ip()
        if self.openstack_release == 'grizzly':
            cmd = 'quantum-netns-cleanup'
        else:
            cmd = 'neutron-netns-cleanup'
        self.migration_utils.execute_command_on_vm(ip_addr, cmd, 'root')

    def clean_lb_pools(self):
        pools = getattr(self.config, 'pools', [])
        pools += itertools.chain(
            *[tenant['pools'] for tenant in self.config.tenants
              if 'pools' in tenant])
        pools_names = [pool['name'] for pool in pools]
        for pool in self.neutronclient.list_pools()['pools']:
            if pool['name'] in pools_names:
                self.neutronclient.delete_pool(pool['id'])
                LOG.info('LBaaS pool "%s" has been deleted', pool['name'])

    def clean_lb_vips(self):
        vips = getattr(self.config, 'vips', [])
        vips += itertools.chain(
            *[tenant['vips'] for tenant in self.config.tenants
              if 'vips' in tenant])
        vips_names = [vip['name'] for vip in vips]
        for vip in self.neutronclient.list_vips()['vips']:
            if vip['name'] in vips_names:
                self.neutronclient.delete_vip(vip['id'])
                LOG.info('LBaaS vip "%s" has been deleted', vip['name'])

    def clean_lb_members(self):
        members = getattr(self.config, 'lb_members', [])
        members += itertools.chain(
            *[tenant['members'] for tenant in self.config.tenants
              if 'members' in tenant])
        member_address = [member['address'] for member in members]
        for member in self.neutronclient.list_members()['members']:
            if member['address'] in member_address:
                self.neutronclient.delete_member(member['id'])
                msg = 'LBaaS member for tenant "%s" has been deleted'
                LOG.info(msg, member['tenant_id'])

    def clean_lbaas_health_monitors(self):
        def check_tenant(tenant_id):
            try:
                self.keystoneclient.tenants.get(tenant_id)
                return True
            except ks_exceptions.NotFound:
                return False

        tenants_ids = [self.get_tenant_id(tenant['name'])
                       for tenant in self.config.tenants
                       if self.tenant_exists(tenant['name'])]
        tenants_ids.append(self.get_tenant_id(self.tenant))
        for hm in self.neutronclient.list_health_monitors()['health_monitors']:
            if hm['tenant_id'] in tenants_ids or not check_tenant(
                    hm['tenant_id']):
                self.neutronclient.delete_health_monitor(hm['id'])
                msg = 'LBaaS health monitor for tenant "%s" has been deleted'
                LOG.info(msg, hm['tenant_id'])

    def clean_server_groups(self):
        server_group_from_config = self.config.server_groups
        for tenant in self.config.tenants:
            if tenant.get('server_groups'):
                server_group_from_config.extend(tenant['server_groups'])
        server_group_names = [sg['name'] for sg in server_group_from_config]
        for server_group in self.get_all_server_groups():
            if server_group.name in server_group_names:
                self.novaclient.server_groups.delete(server_group.id)

    def clean_all_networking(self):
        self.clean_fips()
        self.clean_lb_members()
        self.clean_lb_vips()
        self.clean_lb_pools()
        self.clean_lbaas_health_monitors()
        self.clean_routers()
        self.clean_networks()
        self.clean_namespaces()

    def clean_objects(self):
        self.clean_vms()
        self.clean_flavors()
        self.clean_images()
        self.clean_snapshots()
        self.clean_cinder_snapshots()
        self.clean_volumes()
        self.clean_swift_containers_and_objects()
        self.clean_all_networking()
        self.clean_security_groups()
        self.clean_roles()
        self.clean_keypairs()
        if self.server_groups_supported:
            self.clean_server_groups()
        self.clean_users()
        self.clean_tenants()
