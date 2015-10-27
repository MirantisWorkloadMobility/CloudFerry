import argparse
import itertools
import os
import time
import json
import yaml
import config as conf

from filtering_utils import FilteringUtils

from cinderclient import client as cinder
from glanceclient import Client as glance
from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v2_0 import client as keystone
from neutronclient.common import exceptions as nt_exceptions
from neutronclient.neutron import client as neutron
from novaclient import client as nova
from novaclient import exceptions as nv_exceptions


TIMEOUT = 600
VM_SPAWNING_LIMIT = 5
CREATE_CLEAN_METHODS_MAP = {
    'create_tenants': 'clean_tenants',
    'create_users': 'clean_users',
    'create_roles': 'clean_roles',
    'create_flavors': 'clean_flavors',
    'create_all_networking': 'clean_all_networking'
}
OPENSTACK_RELEASES = {'192.168.1.2': 'grizzly',
                      '192.168.1.3': 'icehouse',
                      '192.168.1.8': 'juno'}


def clean_if_exists(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (ks_exceptions.Conflict,
                nv_exceptions.Conflict,
                nt_exceptions.NeutronClientException):
            print('Method "%s" failed, current resource already exists'
                  % func.__name__)
            clean_method = getattr(self.clean_tools,
                                   CREATE_CLEAN_METHODS_MAP[func.__name__])
            print('Run cleanup method "%s"' % clean_method.__name__)
            clean_method()
            print('Run method "%s" one more time' % func.__name__)
            func(self, *args, **kwargs)
    return wrapper


def retry_until_resources_created(resource_name):
    def actual_decorator(func):
        def wrapper(_list):
            for i in range(TIMEOUT):
                _list = func(_list)
                if _list:
                    time.sleep(1)
                    continue
                else:
                    break
            else:
                msg = '{0}s with ids {1} have not become in active state'
                raise RuntimeError(msg.format(resource_name, _list))
        return wrapper
    return actual_decorator


class NotFound(Exception):
    """Raise this exception in case when resource was not found
    """


class BasePrerequisites(object):

    def __init__(self, config, cloud_prefix='SRC'):
        self.filtering_utils = FilteringUtils()
        self.config = config
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

        self.novaclient = nova.Client(self.config.NOVA_CLIENT_VERSION,
                                      username=self.username,
                                      api_key=self.password,
                                      project_id=self.tenant,
                                      auth_url=self.auth_url)

        self.glanceclient = glance(self.config.GLANCE_CLIENT_VERSION,
                                   endpoint=self.image_endpoint,
                                   token=self.token)

        self.neutronclient = neutron.Client(self.config.NEUTRON_CLIENT_VERSION,
                                            endpoint_url=self.neutron_endpoint,
                                            token=self.token)

        self.cinderclient = cinder.Client(self.config.CINDER_CLIENT_VERSION,
                                          self.username, self.password,
                                          self.tenant, self.auth_url)
        self.openstack_release = self._get_openstack_release()

    def _get_openstack_release(self):
        for release in OPENSTACK_RELEASES:
            if release in self.auth_url:
                return OPENSTACK_RELEASES[release]
        raise RuntimeError('Unknown OpenStack release')

    def get_tenant_id(self, tenant_name):
        for tenant in self.keystoneclient.tenants.list():
            if tenant.name == tenant_name:
                return tenant.id
        raise NotFound('Tenant with name "%s" was not found' % tenant_name)

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

    def get_sg_id(self, sg):
        _sg = self.neutronclient.list_security_groups(
            name=sg, all_tenants=True)['security_groups']
        if _sg:
            return _sg[0]['id']
        raise NotFound('Security group with name "%s" was not found' % sg)

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

    def check_vm_state(self, srv):
        srv = self.novaclient.servers.get(srv)
        return srv.status == 'ACTIVE'

    def tenant_exists(self, tenant_name):
        try:
            self.get_tenant_id(tenant_name)
            return True
        except NotFound:
            return False

    def switch_user(self, user, password, tenant):
        self.keystoneclient = keystone.Client(auth_url=self.auth_url,
                                              username=user,
                                              password=password,
                                              tenant_name=tenant)
        self.keystoneclient.authenticate()
        self.token = self.keystoneclient.auth_token
        self.novaclient = nova.Client(self.config.NOVA_CLIENT_VERSION,
                                      username=user,
                                      api_key=password, project_id=tenant,
                                      auth_url=self.auth_url)
        self.glanceclient = glance(self.config.GLANCE_CLIENT_VERSION,
                                   endpoint=self.image_endpoint,
                                   token=self.token)
        self.neutronclient = neutron.Client(
            self.config.NEUTRON_CLIENT_VERSION,
            endpoint_url=self.neutron_endpoint,
            token=self.token)
        self.cinderclient = cinder.Client(self.config.CINDER_CLIENT_VERSION,
                                          user, password, tenant,
                                          self.auth_url)


class Prerequisites(BasePrerequisites):

    def __init__(self, config, cloud_prefix='SRC'):
        super(Prerequisites, self).__init__(config, cloud_prefix)
        # will be filled during create all networking step
        self.ext_net_id = None
        # object of Prerequisites for dst cloud
        self.dst_cloud = None
        self.clean_tools = CleanEnv(config, cloud_prefix)

    @clean_if_exists
    def create_users(self, users=None):
        def get_params_for_user_creating(_user):
            if 'tenant' in _user:
                _user['tenant_id'] = self.get_tenant_id(_user['tenant'])
            params = ['name', 'password', 'email', 'enabled', 'tenant_id']
            return {param: _user[param] for param in params if param in _user}

        if users is None:
            users = self.config.users
        for user in users:
            self.keystoneclient.users.create(
                **get_params_for_user_creating(user))
            if not user.get('additional_tenants'):
                continue
            for tenant in user['additional_tenants']:
                self.keystoneclient.roles.add_user_role(
                    tenant=self.get_tenant_id(tenant['name']),
                    role=self.get_role_id(tenant['role']),
                    user=self.get_user_id(user['name']))
            # Next action for default sec group creation
            if not user['enabled'] or 'tenant' not in user:
                continue
            self.switch_user(user=user['name'], password=user['password'],
                             tenant=user['tenant'])
            self.novaclient.security_groups.list()
            self.switch_user(user=self.username, password=self.password,
                             tenant=self.tenant)

    @clean_if_exists
    def create_roles(self):
        for role in self.config.roles:
            self.keystoneclient.roles.create(name=role['name'])

    def create_user_tenant_roles(self, user_tenant_roles=None):
        if user_tenant_roles is None:
            user_tenant_roles = self.config.user_tenant_roles
        for user_roles in user_tenant_roles:
            for user, roles in user_roles.iteritems():
                user = self.get_user_id(user)
                for role in roles:
                    self.keystoneclient.roles.add_user_role(
                        user=user, role=self.get_role_id(role['role']),
                        tenant=self.get_tenant_id(role['tenant']))

    @clean_if_exists
    def create_tenants(self, tenants=None):
        if tenants is None:
            tenants = self.config.tenants
        for tenant in tenants:
            self.keystoneclient.tenants.create(tenant_name=tenant['name'],
                                               description=tenant[
                                                   'description'],
                                               enabled=tenant['enabled'])
            self.keystoneclient.roles.add_user_role(
                self.get_user_id(self.username),
                self.get_role_id('admin'),
                self.get_tenant_id(tenant['name']))

    def create_keypairs(self):
        for keypair in self.config.keypairs:
            for _user in self.config.users:
                if _user['name'] == keypair['user']:
                    user = _user
                    break
            else:
                msg = 'User for keypair %s was not found'
                raise RuntimeError(msg % keypair['name'])
            self.switch_user(user=user['name'], password=user['password'],
                             tenant=user['tenant'])
            self.novaclient.keypairs.create(name=keypair['name'],
                                            public_key=keypair['public_key'])
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def modify_quotas(self):
        for tenant in self.config.tenants:
            if 'quota' in tenant:
                self.novaclient.quotas.update(tenant_id=self.get_tenant_id(
                    tenant['name']), **tenant['quota'])

    def upload_image(self):
        @retry_until_resources_created('image')
        def wait_until_images_created(image_ids):
            for img_id in image_ids[:]:
                img = self.glanceclient.images.get(img_id)
                if img.status == 'active':
                    image_ids.remove(img_id)
            return image_ids

        img_ids = []
        for tenant in self.config.tenants:
            if not tenant.get('images'):
                continue
            for image in tenant['images']:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                img = self.glanceclient.images.create(**image)
                img_ids.append(img.id)
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)
        for image in self.config.images:
            img = self.glanceclient.images.create(**image)
            img_ids.append(img.id)
        wait_until_images_created(img_ids)
        src_cloud = Prerequisites(cloud_prefix='SRC', config=self.config)
        src_img = [x.__dict__ for x in
                   src_cloud.glanceclient.images.list()]
        for image in src_img:
            if image['name'] in self.config.img_to_add_members:
                image_id = image['id']
                tenant_list = self.keystoneclient.tenants.list()
                for tenant in tenant_list:
                    tenant = tenant.__dict__
                    if tenant['name'] in self.config.members:
                        member_id = tenant['id']
                        self.glanceclient.image_members.create(image_id,
                                                               member_id)

    def update_filtering_file(self):
        src_cloud = Prerequisites(cloud_prefix='SRC', config=self.config)
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
        for img in self.config.images_not_included_in_filter:
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

    @clean_if_exists
    def create_flavors(self):
        for flavor in self.config.flavors:
            self.novaclient.flavors.create(**flavor)

    def _get_parameters_for_vm_creating(self, vm):
        def get_vm_nics(_vm):
            if 'nics' in _vm:
                for _nic in _vm['nics']:
                    _nic['net-id'] = self.get_net_id(_nic['net-id'])
                return _vm['nics']
            nets = self.neutronclient.list_networks()['networks']
            _t = self.keystoneclient.tenant_id
            nics = [{'net-id': net['id']} for net in nets
                    if not net['router:external'] and net['tenant_id'] == _t]
            return nics
        image_id = self.get_image_id(vm['image']) if vm.get('image') else ''

        return {'image': image_id,
                'flavor': self.get_flavor_id(vm['flavor']),
                'nics': get_vm_nics(vm),
                'name': vm['name'],
                'key_name': vm.get('key_name')
                }

    def create_vms(self):

        def wait_for_vm_creating():
            """ When limit for creating vms in nova is reached, we receive
                exception from nova: 'novaclient.exceptions.OverLimit:
                This request was rate-limited. (HTTP 413)'. To handle this we
                set limit for vm spawning.
            """
            for i in range(TIMEOUT):
                all_vms = self.novaclient.servers.list(
                    search_opts={'all_tenants': 1})
                spawning_vms = [vm.id for vm in all_vms
                                if vm.status == 'BUILD']
                if len(spawning_vms) >= VM_SPAWNING_LIMIT:
                    time.sleep(1)
                else:
                    break
            else:
                raise RuntimeError(
                    'VMs with ids {0} were in "BUILD" state more than {1} '
                    'seconds'.format(spawning_vms, TIMEOUT))

        def create_vms(vm_list):
            vm_ids = []
            for vm in vm_list:
                wait_for_vm_creating()
                _vm = self.novaclient.servers.create(
                    **self._get_parameters_for_vm_creating(vm))
                vm_ids.append(_vm.id)
                if not vm.get('fip'):
                    continue
                wait_until_vms_created([_vm.id])
                fip = self.neutronclient.create_floatingip(
                    {"floatingip": {"floating_network_id": self.ext_net_id}})
                _vm.add_floating_ip(fip['floatingip']['floating_ip_address'])
            return vm_ids

        @retry_until_resources_created('vm')
        def wait_until_vms_created(vm_list):
            for vm in vm_list[:]:
                if self.check_vm_state(vm):
                    vm_list.remove(vm)
            return vm_list

        vms = create_vms(self.config.vms)
        for tenant in self.config.tenants:
            if not tenant.get('vms'):
                continue

            # To create vm with proper keypair, need to switch to right user
            keypairs = set([vm['key_name'] for vm in tenant['vms']
                            if vm.get('key_name')])
            # Split all vms on with and without keypair
            keypairs_vms = {keypair: [] for keypair in keypairs}
            vms_wo_keypairs = []
            for vm in tenant['vms']:
                if vm.get('key_name'):
                    keypairs_vms[vm['key_name']].append(vm)
                else:
                    vms_wo_keypairs.append(vm)
            for keypair in keypairs_vms:
                username = [kp['user'] for kp in self.config.keypairs
                            if kp['name'] == keypair][0]
                user = [user for user in self.config.users
                        if user['name'] == username][0]
                if user['tenant'] != tenant['name']:
                    msg = 'Keypair "{0}" not accessible from tenant "{1}"'
                    raise RuntimeError(msg.format(keypair[0], tenant['name']))
                self.switch_user(user=user['name'], password=user['password'],
                                 tenant=tenant['name'])
                vms.extend(create_vms(keypairs_vms[keypair]))
            # Create vms without keypair
            user = [u for u in self.config.users
                    if u.get('tenant') == tenant['name']][0]
            self.switch_user(user=user['name'], password=user['password'],
                             tenant=tenant['name'])
            vms.extend(create_vms(vms_wo_keypairs))
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

        wait_until_vms_created(vms)

    def create_vm_snapshots(self):
        @retry_until_resources_created('vm_snapshot')
        def wait_until_vm_snapshots_created(snapshot_ids):
            for snp_id in snapshot_ids[:]:
                snp = self.glanceclient.images.get(snp_id)
                if snp.status == 'active':
                    snp_ids.remove(snp_id)
                elif snp.status == 'error':
                    msg = 'Snapshot with id {0} has become in error state'
                    raise RuntimeError(msg.format(snp_id))
            return snapshot_ids

        snp_ids = []
        for snapshot in self.config.snapshots:
            self.novaclient.servers.create_image(
                server=self.get_vm_id(snapshot['server']),
                image_name=snapshot['image_name'])
            snp = self.glanceclient.images.get(self.get_image_id(
                snapshot['image_name']))
            snp_ids.append(snp.id)
        wait_until_vm_snapshots_created(snp_ids)

    def create_networks(self, networks):

        def get_body_for_network_creating(_net):
            # Possible parameters for network creating
            params = ['name', 'admin_state_up', 'shared', 'router:external',
                      'provider:network_type', 'provider:segmentation_id',
                      'provider:physical_network']
            return {param: _net[param] for param in params if param in _net}

        def get_body_for_subnet_creating(_subnet):
            # Possible parameters for subnet creating
            params = ['name', 'cidr', 'allocation_pools', 'dns_nameservers',
                      'host_routes', 'ip_version', 'network_id']
            return {param: _subnet[param] for param in params
                    if param in _subnet}

        for network in networks:
            net = self.neutronclient.create_network(
                {'network': get_body_for_network_creating(network)})
            for subnet in network['subnets']:
                subnet['network_id'] = net['network']['id']
                _subnet = self.neutronclient.create_subnet(
                    {'subnet': get_body_for_subnet_creating(subnet)})
                self.neutronclient.create_port(
                    {"port": {"network_id": net['network']['id']}})
                if not subnet.get('routers_to_connect'):
                    continue
                # If network has attribute routers_to_connect, interface to
                # this network is crated for given router, in case when network
                # is internal and gateway set if - external.
                for router in subnet['routers_to_connect']:
                    router_id = self.get_router_id(router)
                    if network.get('router:external'):
                        self.neutronclient.add_gateway_router(
                            router_id, {"network_id": net['network']['id']})
                    else:
                        self.neutronclient.add_interface_router(
                            router_id, {"subnet_id": _subnet['subnet']['id']})

    def create_routers(self):
        for router in self.config.routers:
            self.neutronclient.create_router(router)

    @clean_if_exists
    def create_all_networking(self):
        self.create_routers()
        self.create_networks(self.config.networks)
        # Getting ip address for real network. This networks will be used to
        # allocation floating ips.
        self.ext_net_id = self.get_net_id(
            [n['name'] for n in self.config.networks
             if n.get('real_network')][0])
        for tenant in self.config.tenants:
            if tenant.get('networks'):
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_networks(tenant['networks'])
            if not tenant.get('unassociated_fip'):
                continue
            for i in range(tenant['unassociated_fip']):
                self.neutronclient.create_floatingip(
                    {"floatingip": {"floating_network_id": self.ext_net_id}})
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

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
        for tenant in self.config.tenants:
            if 'security_groups' in tenant:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_security_group(tenant['security_groups'])
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

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

        @retry_until_resources_created('volume')
        def wait_for_volumes(volume_ids):
            for volume_id in volume_ids[:]:
                _vlm = self.cinderclient.volumes.get(volume_id)
                if _vlm.status == 'available' or _vlm.status == 'in-use':
                    volume_ids.remove(volume_id)
                elif _vlm.status == 'error':
                    msg = 'Volume with id {0} was created with error'
                    raise RuntimeError(msg.format(volume_id))
            return volume_ids

        def get_params_for_volume_creating(_volume):
            params = ['display_name', 'size', 'imageRef']
            if 'image' in _volume:
                _volume['imageRef'] = self.get_image_id(_volume['image'])
            return {param: _volume[param] for param in params
                    if param in _volume}

        vlm_ids = []
        for volume in volumes_list:
            if 'user' in volume:
                user = [u for u in self.config.users
                        if u['name'] == volume['user']][0]
                self.switch_user(user=user['name'], password=user['password'],
                                 tenant=user['tenant'])
            vlm = self.cinderclient.volumes.create(
                **get_params_for_volume_creating(volume))
            vlm_ids.append(vlm.id)
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)
        wait_for_volumes(vlm_ids)
        vlm_ids = []
        for volume in volumes_list:
            if 'server_to_attach' not in volume:
                continue
            vlm_id = self.get_volume_id(volume['display_name'])
            self.novaclient.volumes.create_server_volume(
                server_id=self.get_vm_id(volume['server_to_attach']),
                volume_id=vlm_id,
                device=volume['device'])
            vlm_ids.append(vlm_id)
        wait_for_volumes(vlm_ids)

    def create_cinder_snapshots(self, snapshot_list):
        for snapshot in snapshot_list:
            self.cinderclient.volume_snapshots.create(**snapshot)

    def create_cinder_objects(self):
        self.create_cinder_volumes(self.config.cinder_volumes)
        self.create_cinder_snapshots(self.config.cinder_snapshots)
        for tenant in self.config.tenants:
            if 'cinder_volumes' in tenant:
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_cinder_volumes(tenant['cinder_volumes'])
                if 'cinder_snapshots' in tenant:
                    self.create_cinder_snapshots(tenant['cinder_snapshots'])
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def emulate_vm_states(self):
        for vm_state in self.config.vm_states:
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
                self.novaclient.servers.resize(
                    self.get_vm_id(vm_state['name']), '2')

    def generate_vm_state_list(self):
        data = {}
        for vm in self.novaclient.servers.list(search_opts={'all_tenants': 1}):
            for i in range(TIMEOUT):
                _vm = self.novaclient.servers.get(vm.id)
                if _vm.status != u'RESIZE':
                    break
                time.sleep(1)
            vm_state = self.novaclient.servers.get(vm.id).status
            data[vm.name] = vm_state

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

    def update_network_quotas(self):
        tenants = {ten.name: ten.id
                   for ten in self.keystoneclient.tenants.list()}
        for tenant in self.config.tenants:
            if "quota_network" not in tenant:
                continue
            ten_id = tenants[tenant["name"]]
            quota_net = tenant["quota_network"]
            self.neutronclient.update_quota(ten_id,
                                            {"quota": quota_net})

    def modify_admin_tenant_quotas(self):
        for tenant in self.config.tenants:
            if 'quota' in tenant:
                self.novaclient.quotas.update(tenant_id=self.get_tenant_id(
                    'admin'), **tenant['quota'])
                break

    def delete_users(self):
        for user in self.config.users:
            if user.get('deleted'):
                self.keystoneclient.users.delete(
                    self.get_user_id(user['name']))

    def delete_tenants(self):
        for tenant in self.config.tenants:
            if tenant.get('deleted'):
                self.keystoneclient.tenants.delete(
                    self.get_tenant_id(tenant['name']))

    def create_tenant_wo_sec_group_on_dst(self):
        """
        Method for check fixed issue, when on dst tenant does not have
        security group, even default, while on src this tenant has security
        group.
        """
        self.dst_cloud = Prerequisites(cloud_prefix='DST', config=self.config)
        for t in self.config.tenants:
            if not t.get('deleted') and t['enabled']:
                self.dst_cloud.keystoneclient.tenants.create(
                    tenant_name=t['name'], description=t['description'],
                    enabled=t['enabled'])
                break

    def create_user_on_dst(self):
        """
        Method for check fixed issue, when on dst and src exists user with
        same user tenant role.
        1. Get one user tenant role from config
        2. Get user from config, which should be created
        3. Create roles, which specified in user tenant roles
        4. Get tenants, in which user has roles and tenant which the user
         belongs
        5. Create tenants
        6. Create user
        7. Create user tenant roles
        """
        user_tenant_role = self.config.user_tenant_roles[0]
        username, roles_to_create = user_tenant_role.items()[0]
        user = [user for user in self.config.users
                if username == user['name']][0]
        tenants_names = [user['tenant']]
        for role in roles_to_create:
            self.dst_cloud.keystoneclient.roles.create(name=role['role'])
            if role['tenant'] not in tenants_names:
                tenants_names.append(role['tenant'])

        tenants_to_create = [t for t in self.config.tenants
                             if t['name'] in tenants_names
                             and not self.dst_cloud.tenant_exists(t['name'])]
        self.dst_cloud.create_tenants(tenants_to_create)
        self.dst_cloud.create_users([user])
        self.dst_cloud.create_user_tenant_roles([user_tenant_role])

    def create_volumes_from_images(self):
        self.create_cinder_volumes(self.config.cinder_volumes_from_images)

    def boot_vms_from_volumes(self):
        for vm in self.config.vms_from_volumes:
            params = self._get_parameters_for_vm_creating(vm)
            params['block_device_mapping_v2'] = []
            params['block_device_mapping_v2'].append(
                {'source_type': 'volume',
                 'delete_on_termination': False,
                 'boot_index': 0,
                 'uuid': self.get_volume_id(vm['volume']),
                 'destination_type': 'volume'}
            )
            self.novaclient.servers.create(**params)

    def run_preparation_scenario(self):
        print('>>> Creating tenants:')
        self.create_tenants()
        print('>>> Creating users:')
        self.create_users()
        print('>>> Creating roles:')
        self.create_roles()
        print('>>> Creating user tenant roles:')
        self.create_user_tenant_roles()
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
        if self.openstack_release in ['icehouse', 'juno']:
            print('>>> Create bootable volume from image')
            self.create_volumes_from_images()
            print('>>> Boot vm from volume')
            self.boot_vms_from_volumes()
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
        print('>>> Update network quotas:')
        self.update_network_quotas()
        print('>>> Delete users which should be deleted:')
        self.delete_users()
        print('>>> Delete tenants which should be deleted:')
        self.delete_tenants()
        print('>>> Create tenant on dst, without security group')
        self.create_tenant_wo_sec_group_on_dst()
        print('>>> Create role on dst')
        self.create_user_on_dst()


class CleanEnv(BasePrerequisites):

    def clean_vms(self):
        def wait_until_vms_all_deleted():
            timeout = 120
            for i in range(timeout):
                servers = self.novaclient.servers.list(
                    search_opts={'all_tenants': 1})
                for server in servers:
                    if server.status != 'DELETED':
                        time.sleep(1)
                    try:
                        self.novaclient.servers.delete(server.id)
                    except nv_exceptions.NotFound:
                        pass
                else:
                    break
            else:
                raise RuntimeError('Next vms were not deleted')

        vms = self.config.vms
        vms += itertools.chain(*[tenant['vms'] for tenant
                                 in self.config.tenants if tenant.get('vms')])
        [vms.append(vm) for vm in self.config.vms_from_volumes]
        vms_names = [vm['name'] for vm in vms]
        vms = self.novaclient.servers.list(search_opts={'all_tenants': 1})
        for vm in vms:
            if vm.name not in vms_names:
                continue
            self.novaclient.servers.delete(self.get_vm_id(vm.name))
            print('VM "%s" has been deleted' % vm.name)
        wait_until_vms_all_deleted()

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
            print('Volume "%s" has been deleted' % volume.display_name)

    def clean_flavors(self):
        flavors_names = [flavor['name'] for flavor in self.config.flavors]
        for flavor in self.novaclient.flavors.list():
            if flavor.name not in flavors_names:
                continue
            self.novaclient.flavors.delete(self.get_flavor_id(flavor.name))
            print('Flavor "%s" has been deleted' % flavor.name)

    def clean_images(self):
        images = self.config.images
        images += itertools.chain(*[tenant['images'] for tenant
                                  in self.config.tenants
                                  if tenant.get('images')])
        images_names = [image['name'] for image in images]
        for image in self.glanceclient.images.list():
            if image.name not in images_names:
                continue
            self.glanceclient.images.delete(self.get_image_id(image.name))
            print('Image "%s" has been deleted' % image.name)

    def clean_snapshots(self):
        snaps_names = [snapshot['image_name']
                       for snapshot in self.config.snapshots]
        for snapshot in self.glanceclient.images.list():
            if snapshot.name not in snaps_names:
                continue
            self.glanceclient.images.delete(
                self.get_image_id(snapshot.name))
            print('Snapshot "%s" has been deleted' % snapshot.name)

    def clean_networks(self):
        nets = self.config.networks
        nets += itertools.chain(*[tenant['networks'] for tenant
                                  in self.config.tenants
                                  if tenant.get('networks')])
        nets_names = [net['name'] for net in nets]
        for network in self.neutronclient.list_networks()['networks']:
            if network['name'] not in nets_names:
                continue
            self.neutronclient.delete_network(self.get_net_id(network['name']))
            print('Network "%s" has been deleted' % network['name'])

    def clean_router_ports(self, router_id):
        subnets = self.neutronclient.list_subnets()
        for subnet in subnets['subnets']:
            try:
                self.neutronclient.remove_interface_router(
                    router_id, {'subnet_id': subnet['id']})
            except nt_exceptions.NeutronClientException:
                pass

    def clean_routers(self):
        router_names = [router['router']['name']
                        for router in self.config.routers]
        for router in self.neutronclient.list_routers()['routers']:
            if router['name'] not in router_names:
                continue
            router_id = self.get_router_id(router['name'])
            self.clean_router_ports(router_id)
            self.neutronclient.delete_router(router_id)
            print('Router "%s" has been deleted' % router['name'])

    def clean_fips(self):
        floatingips = self.neutronclient.list_floatingips()['floatingips']
        for ip in floatingips:
            try:
                self.neutronclient.delete_floatingip(ip['id'])
            except Exception as e:
                print "Ip %s failed to delete: %s" % (
                    ip['floating_ip_address'], repr(e))

    def clean_security_groups(self):
        sgs = self.neutronclient.list_security_groups()['security_groups']
        for sg in sgs:
            try:
                self.neutronclient.delete_security_group(self.get_sg_id(
                                                         sg['name']))
            except (nt_exceptions.NeutronClientException,
                    NotFound) as e:
                print "Security group %s failed to delete: %s" % (sg['name'],
                                                                  repr(e))

    def clean_roles(self):
        roles_names = [role['name'] for role in self.config.roles]
        for role in self.keystoneclient.roles.list():
            if role.name not in roles_names:
                continue
            self.keystoneclient.roles.delete(self.get_role_id(role.name))
            print('Role "%s" has been deleted' % role.name)

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
                map(self.novaclient.keypairs.delete, keypairs)
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
            print('User "%s" has been deleted' % user.name)

    def clean_tenants(self):
        tenants_names = [tenant['name'] for tenant in self.config.tenants]
        for tenant in self.keystoneclient.tenants.list():
            if tenant.name not in tenants_names:
                continue
            self.keystoneclient.tenants.delete(self.get_tenant_id(tenant.name))
            print('Tenant "%s" has been deleted' % tenant.name)

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
            print('Snapshot "%s" has been deleted' % snapshot.display_name)

    def clean_all_networking(self):
        self.clean_fips()
        self.clean_routers()
        self.clean_networks()

    def clean_objects(self):
        self.clean_vms()
        self.clean_flavors()
        self.clean_images()
        self.clean_snapshots()
        self.clean_cinder_snapshots()
        self.clean_volumes()
        self.clean_all_networking()
        self.clean_security_groups()
        self.clean_roles()
        self.clean_keypairs()
        self.clean_users()
        self.clean_tenants()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to generate load for Openstack and delete '
                    'generated objects')
    parser.add_argument('--clean', help='clean objects described in '
                                        'self.config.ini', action='store_true')
    parser.add_argument('--env', default='SRC',
                        help='choose cloud: SRC or DST')
    args = parser.parse_args()
    preqs = Prerequisites(config=conf, cloud_prefix=args.env)
    if args.clean:
        preqs.clean_tools.clean_objects()
    else:
        preqs.run_preparation_scenario()
