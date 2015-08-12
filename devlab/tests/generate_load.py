import argparse
import itertools
import os
import time
import json
import yaml

from glanceclient import Client as glance
from novaclient import client as nova
from neutronclient.neutron import client as neutron
from keystoneclient.v2_0 import client as keystone
from cinderclient import client as cinder

import config
from filtering_utils import FilteringUtils

NOVA_CLIENT_VERSION = config.NOVA_CLIENT_VERSION
GLANCE_CLIENT_VERSION = config.GLANCE_CLIENT_VERSION
NEUTRON_CLIENT_VERSION = config.NEUTRON_CLIENT_VERSION
CINDER_CLIENT_VERSION = config.CINDER_CLIENT_VERSION


class Prerequisites(object):
    def __init__(self, cloud_prefix='SRC'):
        self.filtering_utils = FilteringUtils()
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

        self.cinderclient = cinder.Client(CINDER_CLIENT_VERSION, self.username,
                                          self.password, self.tenant,
                                          self.auth_url)

    def get_tenant_id(self, tenant_name):
        tenants = self.keystoneclient.tenants.list()
        return [x for x in tenants if x.name == tenant_name][0].id

    def get_user_id(self, user_name):
        users = self.keystoneclient.users.list()
        return [x for x in users if x.name == user_name][0].id

    def get_router_id(self, router):
        return self.neutronclient.list_routers(name=router)['routers'][0]['id']

    def get_image_id(self, image_name):
        images = self.glanceclient.images.list()
        return [x for x in images if x.name == image_name][0].id

    def get_flavor_id(self, flavor_name):
        flavors = self.novaclient.flavors.list()
        return [x for x in flavors if x.name == flavor_name][0].id

    def get_vm_id(self, vm_name):
        vms = self.novaclient.servers.list(search_opts={'all_tenants': 1})
        return [x for x in vms if x.name == vm_name][0].id

    def get_role_id(self, role):
        roles = self.keystoneclient.roles.list()
        return [x for x in roles if x.name == role][0].id

    def get_net_id(self, net):
        return self.neutronclient.list_networks(
            name=net, all_tenants=True)['networks'][0]['id']

    def get_sg_id(self, sg):
        return self.neutronclient.list_security_groups(
            name=sg, all_tenants=True)['security_groups'][0]['id']

    def get_volume_id(self, volume_name):
        volumes = self.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        return [x for x in volumes if x.display_name == volume_name][0].id

    def get_volume_snapshot_id(self, snapshot_name):
        snapshots = self.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})
        return [x for x in snapshots if x.display_name == snapshot_name][0].id

    def check_vm_state(self, srv):
        while srv.status != 'ACTIVE':
                time.sleep(2)
                srv = self.novaclient.servers.get(srv.id)
                if srv.status == 'ERROR':
                    return None

    def wait_for_volume(self, volume_name):
        vlm = self.cinderclient.volumes.get(self.get_volume_id(volume_name))
        while vlm.status != 'available' and vlm.status != 'in-use':
            time.sleep(2)
            vlm = self.cinderclient.volumes.get(
                self.get_volume_id(volume_name))
            if vlm.status == 'error':
                    return None

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
        self.cinderclient = cinder.Client(CINDER_CLIENT_VERSION, user,
                                          password, tenant, self.auth_url)

    def create_users(self):
        for user in config.users:
            self.keystoneclient.users.create(name=user['name'],
                                             password=user['password'],
                                             email=user['email'],
                                             enabled=user['enabled'],
                                             tenant_id=self.get_tenant_id(
                                                 user['tenant']))

    def create_roles(self):
        for role in config.roles:
            self.keystoneclient.roles.create(name=role['name'])

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
            self.switch_user(user=user['name'], password=user['password'],
                             tenant=user['tenant'])
            self.novaclient.keypairs.create(**keypair)
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
        src_cloud = Prerequisites(cloud_prefix='SRC')
        src_img = [x.__dict__ for x in
                   src_cloud.glanceclient.images.list()]
        for image in src_img:
            if image['name'] in config.img_to_add_members:
                image_id = image['id']
                tenant_list = self.keystoneclient.tenants.list()
                for tenant in tenant_list:
                    tenant = tenant.__dict__
                    if tenant['name'] in config.members:
                        member_id = tenant['id']
                        self.glanceclient.image_members.create(image_id,
                                                               member_id)

    def update_filtering_file(self):
        src_cloud = Prerequisites(cloud_prefix='SRC')
        src_img = [x.__dict__ for x in
                   src_cloud.glanceclient.images.list()]
        src_vms = [x.__dict__ for x in
                   src_cloud.novaclient.servers.list(
                       search_opts={'all_tenants': 1})]
        image_dict = {}
        for image in src_img:
            img_members = self.glanceclient.image_members.list(image['id'])
            if len(img_members) > 1:
                img_mem_list = []
                for img_member in img_members:
                    img_member = img_member.__dict__
                    img_mem_list.append(img_member['member_id'])
                image_dict[image['id']] = img_mem_list
        vm_id_list = []
        for vm in src_vms:
            vm_id = vm['id']
            vm_id_list.append(vm_id)
        loaded_data = self.filtering_utils.load_file('configs/filter.yaml')
        filter_dict = loaded_data[0]
        if filter_dict is None:
            filter_dict = {'images': {'images_list': {}},
                           'instances': {'id': {}}}
        all_img_ids = []
        img_list = []
        not_incl_img = []
        vm_list = []
        for image in src_img:
            all_img_ids.append(image['id'])
        for img in config.images_not_included_in_filter:
            not_incl_img.append(self.get_image_id(img))
        for key in filter_dict.keys():
            if key == 'images':
                for img_id in all_img_ids:
                    if img_id not in not_incl_img:
                        img_list.append(img_id)
                filter_dict[key]['images_list'] = img_list
            elif key == 'instances':
                for vm in vm_id_list:
                    if vm != self.get_vm_id('not_in_filter'):
                        vm_list.append(vm)
                filter_dict[key]['id'] = vm_list
        file_path = loaded_data[1]
        with open(file_path, "w") as f:
            yaml.dump(filter_dict, f, default_flow_style=False)

    def create_flavors(self):
        for flavor in config.flavors:
            self.novaclient.flavors.create(**flavor)

    def create_vms(self):
        for vm in config.vms:
            vm['image'] = self.get_image_id(vm['image'])
            vm['flavor'] = self.get_flavor_id(vm['flavor'])
            self.check_vm_state(self.novaclient.servers.create(**vm))
        for tenant in config.tenants:
            if 'vms' in tenant:
                for user in config.users:
                    if 'deleted' in user and user['deleted']:
                        continue
                    if user['tenant'] == tenant['name'] and user['enabled']:
                        self.switch_user(user=user['name'],
                                         password=user['password'],
                                         tenant=user['tenant'])
                for vm in tenant['vms']:
                    vm['image'] = self.get_image_id(vm['image'])
                    vm['flavor'] = self.get_flavor_id(vm['flavor'])
                    if 'nics' in vm:
                        for nic in vm['nics']:
                            nic['net-id'] = self.get_net_id(nic['net-id'])
                    self.check_vm_state(self.novaclient.servers.create(**vm))
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
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

    def get_sec_group_id_by_tenant_id(self, tenant_id):
        sec_group_list = self.neutronclient.list_security_groups()
        return [i['id'] for i in sec_group_list['security_groups']
                if i['tenant_id'] == tenant_id]

    def create_security_group_rule(self, group_id, tenant_id, protocol='tcp',
                                   port_range_min=22, port_range_max=22,
                                   direction='ingress'):
        sec_rule = {'security_group_rule': {"security_group_id": group_id,
                                            "protocol": protocol,
                                            "direction": direction,
                                            'tenant_id': tenant_id,
                                            "port_range_min": port_range_min,
                                            "port_range_max": port_range_max}}
        self.neutronclient.create_security_group_rule(sec_rule)

    def create_cinder_volumes(self, volumes_list):
        for volume in volumes_list:
            if 'user' in volume:
                user = [u for u in config.users
                        if u['name'] == volume['user']][0]
                self.switch_user(user=user['name'], password=user['password'],
                                 tenant=user['tenant'])
            vlm = self.cinderclient.volumes.create(display_name=volume['name'],
                                                   size=volume['size'])
            self.wait_for_volume(volume['name'])
            if 'server_to_attach' in volume:
                self.novaclient.volumes.create_server_volume(
                    server_id=self.get_vm_id(volume['server_to_attach']),
                    volume_id=vlm.id,
                    device=volume['device'])
            self.wait_for_volume(volume['name'])

    def create_cinder_snapshots(self, snapshot_list):
        for snapshot in snapshot_list:
            self.cinderclient.volume_snapshots.create(**snapshot)

    def create_cinder_objects(self):
        self.create_cinder_volumes(config.cinder_volumes)
        self.create_cinder_snapshots(config.cinder_snapshots)
        for tenant in config.tenants:
            if 'cinder_volumes' in tenant:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_cinder_volumes(tenant['cinder_volumes'])
                if 'cinder_snapshots' in tenant:
                    self.create_cinder_snapshots(tenant['cinder_snapshots'])
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def emulate_vm_states(self):
        for vm_state in config.vm_states:
            # emulate error state:
            if vm_state['state'] == u'error':
                self.novaclient.servers.reset_state(
                    server=self.get_vm_id(vm_state['name']),
                    state=vm_state['state'])
            # emulate suspend state:
            elif vm_state['state'] == u'suspend':
                self.novaclient.servers.suspend(self.get_vm_id(
                    vm_state['name']))
            # emulate resize state:
            elif vm_state['state'] == u'pause':
                self.novaclient.servers.pause(self.get_vm_id(vm_state['name']))
            # emulate stop/shutoff state:
            elif vm_state['state'] == u'stop':
                self.novaclient.servers.stop(self.get_vm_id(vm_state['name']))
            # emulate resize state:
            elif vm_state['state'] == u'resize':
                self.novaclient.servers.resize(self.get_vm_id(vm_state['name']),
                                               '1')

    def generate_vm_state_list(self):
        data = {}
        for vm in self.novaclient.servers.list():
            vm_name = vm.name
            index = self.novaclient.servers.list().index(vm)
            while self.novaclient.servers.list()[index].status == u'RESIZE':
                time.sleep(2)
            vm_state = self.novaclient.servers.list()[index].status
            data[vm_name] = vm_state
        file_name = 'pre_migration_vm_states.json'
        with open(file_name, 'w') as outfile:
            json.dump(data, outfile, sort_keys=True, indent=4,
                      ensure_ascii=False)

    def delete_flavor(self, flavor='del_flvr'):
        """
        Method for flavor deletion.
        """
        try:
            self.novaclient.flavors.delete(
                self.get_flavor_id(flavor))
        except Exception as e:
            print "Flavor %s failed to delete: %s" % (flavor, repr(e))

    def modify_admin_tenant_quotas(self):
        for tenant in config.tenants:
            if 'quota' in tenant:
                self.novaclient.quotas.update(tenant_id=self.get_tenant_id(
                    'admin'), **tenant['quota'])
                break

    def delete_users(self):
        for user in config.users:
            if user.get('deleted'):
                self.keystoneclient.users.delete(
                    self.get_user_id(user['name']))

    def run_preparation_scenario(self):
        print('>>> Creating tenants:')
        self.create_tenants()
        print('>>> Creating users:')
        self.create_users()
        print('>>> Creating roles:')
        self.create_roles()
        print('>>> Creating keypairs:')
        self.create_keypairs()
        print('>>> Modifying quotas:')
        self.modify_quotas()
        print('>>> Creating flavors:')
        self.create_flavors()
        print('>>> Uploading images:')
        self.upload_image()
        print('>>> Creating networking:')
        self.create_all_networking()
        print('>>> Creating vms:')
        self.create_vms()
        print('>>> Updating filtering:')
        self.update_filtering_file()
        print('>>> Creating vm snapshots:')
        self.create_vm_snapshots()
        print('>>> Creating security groups:')
        self.create_security_groups()
        print('>>> Creating cinder objects:')
        self.create_cinder_objects()
        print('>>> Emulating vm states:')
        self.emulate_vm_states()
        print('>>> Generating vm states list:')
        self.generate_vm_state_list()
        print('>>> Deleting flavor:')
        self.delete_flavor()
        print('>>> Modifying admin tenant quotas:')
        self.modify_admin_tenant_quotas()
        print('>>> Delete users which should be deleted:')
        self.delete_users()

    def clean_objects(self):
        for flavor in config.flavors:
            try:
                self.novaclient.flavors.delete(
                    self.get_flavor_id(flavor['name']))
            except Exception as e:
                print "Flavor %s failed to delete: %s" % (flavor['name'],
                                                          repr(e))
        vms = config.vms
        vms += itertools.chain(*[tenant['vms'] for tenant
                                 in config.tenants if tenant['vms']])
        for vm in vms:
            try:
                self.novaclient.servers.delete(self.get_vm_id(vm['name']))
            except Exception as e:
                print "VM %s failed to delete: %s" % (vm['name'], repr(e))
        for image in config.images:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(image['name']))
            except Exception as e:
                print "Image %s failed to delete: %s" % (image['name'],
                                                         repr(e))
        nets = config.networks
        nets += itertools.chain(*[tenant['networks'] for tenant
                                  in config.tenants if tenant['networks']])
        floatingips = self.neutronclient.list_floatingips()['floatingips']
        for ip in floatingips:
            try:
                self.neutronclient.delete_floatingip(ip['id'])
            except Exception as e:
                print "Ip %s failed to delete: %s" % (
                    ip['floating_ip_address'], repr(e))
        for router in config.routers:
            try:
                self.neutronclient.delete_router(self.get_router_id(
                    router['router']['name']))
            except Exception as e:
                print "Router failed to delete: %s" % repr(e)
        for network in nets:
            try:
                self.neutronclient.delete_network(self.get_net_id(
                    network['name']))
            except Exception as e:
                print "Network %s failed to delete: %s" % (network['name'],
                                                           repr(e))
        for snapshot in config.snapshots:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(snapshot['image_name']))
            except Exception as e:
                print "Image %s failed to delete: %s" % (
                    snapshot['image_name'], repr(e))
        for tenant in config.tenants:
            try:
                self.keystoneclient.tenants.delete(
                    self.get_tenant_id(tenant['name']))
            except Exception as e:
                print "Tenant %s failed to delete: %s" % (tenant['name'],
                                                          repr(e))
        sgs = self.neutronclient.list_security_groups()['security_groups']
        for sg in sgs:
            try:
                print "delete sg {}".format(sg['name'])
                self.neutronclient.delete_security_group(self.get_sg_id(
                                                         sg['name']))
            except Exception as e:
                print "Security group %s failed to delete: %s" % (sg['name'],
                                                                  repr(e))
        for user in config.users:
            try:
                self.keystoneclient.users.delete(
                    self.get_user_id(user['name']))
            except Exception as e:
                print "User %s failed to delete: %s" % (user['name'], repr(e))
        for role in config.roles:
            try:
                self.keystoneclient.roles.delete(self.get_role_id(
                    role['name']))
            except Exception as e:
                print "Role %s failed to delete: %s" % (role['name'], repr(e))
        snapshots = config.cinder_snapshots
        snapshots += itertools.chain(*[tenant['cinder_snapshots'] for tenant
                                       in config.tenants if 'cinder_snapshots'
                                       in tenant])
        for snapshot in snapshots:
            try:
                self.cinderclient.volume_snapshots.delete(
                    self.get_volume_snapshot_id(snapshot['display_name']))
            except Exception as e:
                print "Snapshot %s failed to delete: %s" % (
                    snapshot['display_name'], repr(e))
        volumes = config.cinder_volumes
        volumes += itertools.chain(*[tenant['cinder_volumes'] for tenant
                                     in config.tenants if 'cinder_volumes'
                                     in tenant])
        for volume in volumes:
            try:
                self.cinderclient.volumes.delete(
                    self.get_volume_id(volume['name']))
            except Exception as e:
                print "Volume %s failed to delete: %s" % (volume['name'],
                                                          repr(e))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to generate load for Openstack and delete '
                    'generated objects')
    parser.add_argument('--clean', help='clean objects described in '
                                        'config.ini', action='store_true')
    parser.add_argument('--env', default='SRC', help='choose cloud: SRC or DST')
    args = parser.parse_args()
    preqs = Prerequisites(cloud_prefix=args.env)
    if args.clean:
        preqs.clean_objects()
    else:
        preqs.run_preparation_scenario()
