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

    def create_users(self):
        for user in config.users:
            self.keystoneclient.users.create(name=user['name'],
                                             password=user['pass'],
                                             email=user['email'],
                                             enabled=user['enabled'],
                                             tenant_id=self.get_tenant_id(
                                                 user['tenant']))

    def change_user(self, user, password, tenant):
        self.novaclient = nova.Client(NOVA_CLIENT_VERSION, username=user,
                                      api_key=password, project_id=tenant,
                                      auth_url=self.auth_url)

    def create_tenants(self):
        for tenant in config.tenants:
            self.keystoneclient.tenants.create(tenant_name=tenant['name'],
                                               description=tenant[
                                                   'description'],
                                               enabled=tenant['enabled'])

    def get_tenant_id(self, tenant_name):
        tenants = self.keystoneclient.tenants.list()
        my_tenant = [x for x in tenants if x.name == tenant_name][0]
        return my_tenant.id

    def get_image_id(self, image_name):
        images = self.glanceclient.images.list()
        my_image = [x for x in images if x.name == image_name][0]
        return my_image.id

    def get_flavor_id(self, flavor_name):
        flavors = self.novaclient.flavors.list()
        my_flavor = [x for x in flavors if x.name == flavor_name][0]
        return my_flavor.id

    def get_vm_id(self, vm_name):
        vms = self.novaclient.servers.list()
        my_vm = [x for x in vms if x.name == vm_name][0]
        return my_vm.id

    def create_keypairs(self):
        for user, keypair in zip(config.users, config.keypairs):
            self.change_user(user=user['name'], password=user['pass'],
                             tenant=user['tenant'])
            self.novaclient.keypairs.create(name=keypair['name'],
                                            public_key=keypair['pub'])
        self.change_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def modify_quotas(self):
        for tenant, quota in zip(config.tenants, config.quotas):
            self.novaclient.quotas.update(tenant_id=self.get_tenant_id(
                tenant['name']), **quota)

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
            srv = self.novaclient.servers.create(name=vm['name'],
                                                 image=self.get_image_id(
                                                     vm['image']),
                                                 flavor=self.get_flavor_id(
                                                     vm['flavor']))
            while srv.status != 'ACTIVE':
                time.sleep(2)
                srv = self.novaclient.servers.get(srv.id)
                if srv.status == 'ERROR':
                    break

    def create_vm_snapshots(self):
        for snapshot in config.snapshots:
            self.novaclient.servers.create_image(
                server=self.get_vm_id(snapshot['server']),
                image_name=snapshot['image_name'])

    def create_networks(self):
        for network, subnet in zip(config.networks, config.subnets):
            net = self.neutronclient.create_network({'network': network})
            subnet['network_id'] = net['network']['id']
            self.neutronclient.create_subnet({'subnet': subnet})

    def run_preparation_scenario(self):
        self.create_tenants()
        self.create_users()
        self.create_keypairs()
        self.modify_quotas()
        self.create_flavors()
        self.upload_image()
        self.create_vms()
        self.create_vm_snapshots()
        self.create_networks()


if __name__ == '__main__':
    preqs = Prerequisites()
    preqs.run_preparation_scenario()
