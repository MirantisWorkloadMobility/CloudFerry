import argparse
import itertools
import os
import time

from glanceclient import Client as glance
from novaclient import client as nova
from neutronclient.neutron import client as neutron
from keystoneclient.v2_0 import client as keystone

import config

NOVA_CLIENT_VERSION = config.NOVA_CLIENT_VERSION
GLANCE_CLIENT_VERSION = config.GLANCE_CLIENT_VERSION
NEUTRON_CLIENT_VERSION = config.NEUTRON_CLIENT_VERSION


class Prerequisites():
    def __init__(self, cloud_prefix='SRC'):
        self.username = os.environ['%s_OS_USERNAME' % cloud_prefix]
        self.password = os.environ['%s_OS_PASSWORD' % cloud_prefix]
        self.tenant = os.environ['%s_OS_TENANT_NAME' % cloud_prefix]
        self.auth_url = os.environ['%s_OS_AUTH_URL' % cloud_prefix]
        self.image_endpoint = os.environ['%s_OS_IMAGE_ENDPOINT' % cloud_prefix]
        self.neutron_endpoint = os.environ['%s_OS_NEUTRON_ENDPOINT'
                                           % cloud_prefix]

        self.keystoneclient = keystone.Client(auth_url=self.auth_url,
                                              username=self.username,
                                              password=self.password,
                                              tenant_name=self.tenant)
        self.keystoneclient.authenticate()
        self.token = self.keystoneclient.auth_token

        self.novaclient = nova.Client(NOVA_CLIENT_VERSION,
                                      username=self.username,
                                      api_key=self.password,
                                      project_id=self.tenant,
                                      auth_url=self.auth_url)

        self.glanceclient = glance(GLANCE_CLIENT_VERSION,
                                   endpoint=self.image_endpoint,
                                   token=self.token)

        self.neutronclient = neutron.Client(NEUTRON_CLIENT_VERSION,
                                            endpoint_url=self.neutron_endpoint,
                                            token=self.token)

    def get_tenant_id(self, tenant_name):
        tenants = self.keystoneclient.tenants.list()
        return [x for x in tenants if x.name == tenant_name][0].id

    def get_user_id(self, user_name):
        users = self.keystoneclient.users.list()
        return [x for x in users if x.name == user_name][0].id

    def get_image_id(self, image_name):
        images = self.glanceclient.images.list()
        return [x for x in images if x.name == image_name][0].id

    def get_flavor_id(self, flavor_name):
        flavors = self.novaclient.flavors.list()
        return [x for x in flavors if x.name == flavor_name][0].id

    def get_vm_id(self, vm_name):
        vms = self.novaclient.servers.list()
        return [x for x in vms if x.name == vm_name][0].id

    def get_role_id(self, role):
        roles = self.keystoneclient.roles.list()
        return [x for x in roles if x.name == role][0].id

    def get_net_id(self, net):
        return self.neutronclient.list_networks(
            name=net)['networks'][0]['id']

    def check_vm_state(self, srv):
        while srv.status != 'ACTIVE':
                time.sleep(2)
                srv = self.novaclient.servers.get(srv.id)
                if srv.status == 'ERROR':
                    return None

    def create_users(self):
        for user in config.users:
            self.keystoneclient.users.create(name=user['name'],
                                             password=user['pass'],
                                             email=user['email'],
                                             enabled=user['enabled'],
                                             tenant_id=self.get_tenant_id(
                                                 user['tenant']))

    def switch_user(self, user, password, tenant):
        self.keystoneclient = keystone.Client(auth_url=self.auth_url,
                                              username=user,
                                              password=password,
                                              tenant_name=tenant)
        self.keystoneclient.authenticate()
        self.token = self.keystoneclient.auth_token
        self.novaclient = nova.Client(NOVA_CLIENT_VERSION, username=user,
                                      api_key=password, project_id=tenant,
                                      auth_url=self.auth_url)
        self.glanceclient = glance(GLANCE_CLIENT_VERSION,
                                   endpoint=self.image_endpoint,
                                   token=self.token)
        self.neutronclient = neutron.Client(
            NEUTRON_CLIENT_VERSION,
            endpoint_url=self.neutron_endpoint,
            token=self.token)

    def create_tenants(self):
        for tenant in config.tenants:
            self.keystoneclient.tenants.create(tenant_name=tenant['name'],
                                               description=tenant[
                                                   'description'],
                                               enabled=tenant['enabled'])
            self.keystoneclient.roles.add_user_role(
                self.get_user_id(self.username),
                self.get_role_id('admin'),
                self.get_tenant_id(tenant['name']))

    def create_keypairs(self):
        for user, keypair in zip(config.users, config.keypairs):
            self.switch_user(user=user['name'], password=user['pass'],
                             tenant=user['tenant'])
            self.novaclient.keypairs.create(name=keypair['name'],
                                            public_key=keypair['pub'])
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def modify_quotas(self):
        for tenant in config.tenants:
            if 'quota' in tenant:
                self.novaclient.quotas.update(tenant_id=self.get_tenant_id(
                    tenant['name']), **tenant['quota'])

    def upload_image(self):
        for image in config.images:
            img = self.glanceclient.images.create(**image)
            while img.status != 'active':
                time.sleep(2)
                img = self.glanceclient.images.get(img.id)

    def create_flavors(self):
        for flavor in config.flavors:
            self.novaclient.flavors.create(name=flavor['name'],
                                           disk=flavor['disk'],
                                           ram=flavor['ram'],
                                           vcpus=flavor['vcpus'])

    def create_vms(self):
        for vm in config.vms:
            self.check_vm_state(
                self.novaclient.servers.create(name=vm['name'],
                                               image=self.get_image_id(
                                                   vm['image']),
                                               flavor=self.get_flavor_id(
                                                   vm['flavor'])))
        for tenant in config.tenants:
            if tenant['vms']:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                for vm in tenant['vms']:
                    self.check_vm_state(
                        self.novaclient.servers.create(
                            name=vm['name'],
                            image=self.get_image_id(vm['image']),
                            flavor=self.get_flavor_id(vm['flavor'])))
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def create_vm_snapshots(self):
        for snapshot in config.snapshots:
            self.novaclient.servers.create_image(
                server=self.get_vm_id(snapshot['server']),
                image_name=snapshot['image_name'])

    def create_networks(self, network_list, subnet_list):
        for network, subnet in zip(network_list, subnet_list):
            net = self.neutronclient.create_network({'network': network})
            subnet['network_id'] = net['network']['id']
            self.neutronclient.create_subnet({'subnet': subnet})

    def create_router(self, router_list):
        for router in router_list:
            router['router']['external_gateway_info']['network_id'] = \
                self.get_net_id(
                    router['router']['external_gateway_info']['network_id'])
            self.neutronclient.create_router(router)

    def create_all_networking(self):
        self.create_networks(config.networks, config.subnets)
        ext_net_id = [self.get_net_id(net['name']) for net in config.networks
                      if 'router:external' in net and net['router:external']
                      ][0]
        for tenant in config.tenants:
            if tenant['networks']:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_networks(tenant['networks'], tenant['subnets'])
                self.neutronclient.create_floatingip(
                    {"floatingip": {"floating_network_id": ext_net_id}})
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)
        self.create_router(config.routers)

    def create_security_group(self, sg_list):
        for security_group in sg_list:
            gid = self.novaclient.security_groups.create(
                name=security_group['name'],
                description=security_group['description']).id
            if 'rules' in security_group:
                for rule in security_group['rules']:
                    self.novaclient.security_group_rules.create(
                        gid,
                        ip_protocol=rule['ip_protocol'],
                        from_port=rule['from_port'], to_port=rule['to_port'],
                        cidr=rule['cidr'])

    def create_security_groups(self):
        for tenant in config.tenants:
            if 'security_groups' in tenant:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_security_group(tenant['security_groups'])
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def run_preparation_scenario(self):
        self.create_tenants()
        self.create_users()
        self.create_keypairs()
        self.modify_quotas()
        self.create_flavors()
        self.upload_image()
        self.create_all_networking()
        self.create_vms()
        self.create_vm_snapshots()
        self.create_security_groups()

    def clean_objects(self):
        for flavor in config.flavors:
            try:
                self.novaclient.flavors.delete(
                    self.get_flavor_id(flavor['name']))
            except Exception as e:
                print "Flavor %s failed to delete" % flavor['name']
                print repr(e)
        vms = config.vms
        vms += itertools.chain(*[tenant['vms'] for tenant
                                 in config.tenants if tenant['vms']])
        for vm in vms:
            try:
                self.novaclient.servers.delete(self.get_vm_id(vm['name']))
            except Exception as e:
                print "VM %s failed to delete" % vm['name']
                print repr(e)
        for image in config.images:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(image['name']))
            except Exception as e:
                print "Image %s failed to delete" % image['name']
                print repr(e)
        nets = config.networks
        nets += itertools.chain(*[tenant['networks'] for tenant
                                  in config.tenants if tenant['networks']])
        for network in nets:
            try:
                self.neutronclient.delete_network(self.get_net_id(
                    network['name']))
            except Exception as e:
                print "Network %s failed to delete" % network['name']
                print repr(e)
        for snapshot in config.snapshots:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(snapshot['image_name']))
            except Exception as e:
                print "Image %s failed to delete" % snapshot['image_name']
                print repr(e)
        for tenant in config.tenants:
            try:
                self.keystoneclient.tenants.delete(
                    self.get_tenant_id(tenant['name']))
            except Exception as e:
                print "Tenant %s failed to delete" % tenant['name']
                print repr(e)
        for user in config.users:
            try:
                self.keystoneclient.users.delete(
                    self.get_user_id(user['name']))
            except Exception as e:
                print "User %s failed to delete" % user['name']
                print repr(e)


if __name__ == '__main__':
    preqs = Prerequisites()
    parser = argparse.ArgumentParser(
        description='Script to generate load for Openstack and delete '
                    'generated objects')
    parser.add_argument('--clean', help='clean objects described in '
                                        'config.ini', action='store_true')
    args = parser.parse_args()
    if args.clean:
        preqs.clean_objects()
    else:
        preqs.run_preparation_scenario()
