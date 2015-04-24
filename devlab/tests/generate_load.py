import argparse
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
        my_tenant = [x for x in tenants if x.name == tenant_name][0]
        return my_tenant.id

    def get_user_id(self, user_name):
        users = self.keystoneclient.users.list()
        my_user = [x for x in users if x.name == user_name][0]
        return my_user.id

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
        self.create_networks()
        self.create_vms()
        self.create_vm_snapshots()

    def clean_objects(self):
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
        for flavor in config.flavors:
            try:
                self.novaclient.flavors.delete(
                    self.get_flavor_id(flavor['name']))
            except Exception as e:
                print "Flavor %s failed to delete" % flavor['name']
                print repr(e)
        for vm in config.vms:
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
        for network in config.networks:
            try:
                nets = self.neutronclient.list_networks(name=network['name'])
                self.neutronclient.delete_network(nets['networks'][0]['id'])
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
