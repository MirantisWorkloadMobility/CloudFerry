import argparse
import itertools
import os
import time
import json
import yaml
import config as conf

from neutronclient.common.exceptions import NeutronClientException
from keystoneclient.exceptions import Unauthorized
from novaclient.exceptions import NotFound
from glanceclient import Client as glance
from novaclient import client as nova
from neutronclient.neutron import client as neutron
from keystoneclient.v2_0 import client as keystone
from cinderclient import client as cinder
from filtering_utils import FilteringUtils


TIMEOUT = 600
VM_SPAWNING_LIMIT = 5


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


class Prerequisites(object):
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
        # will be filled during create all networking step
        self.ext_net_id = None

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

    def check_vm_state(self, srv):
        srv = self.novaclient.servers.get(srv)
        return srv.status == 'ACTIVE'

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

    def create_users(self):
        def get_params_for_user_creating(_user):
            if 'tenant' in _user:
                _user['tenant_id'] = self.get_tenant_id(_user['tenant'])
            params = ['name', 'password', 'email', 'enabled', 'tenant_id']
            return {param: _user[param] for param in params if param in _user}

        for user in self.config.users:
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

    def create_roles(self):
        for role in self.config.roles:
            self.keystoneclient.roles.create(name=role['name'])

    def create_tenants(self):
        for tenant in self.config.tenants:
            self.keystoneclient.tenants.create(tenant_name=tenant['name'],
                                               description=tenant[
                                                   'description'],
                                               enabled=tenant['enabled'])
            self.keystoneclient.roles.add_user_role(
                self.get_user_id(self.username),
                self.get_role_id('admin'),
                self.get_tenant_id(tenant['name']))

    def create_keypairs(self):
        for user, keypair in zip(self.config.users, self.config.keypairs):
            self.switch_user(user=user['name'], password=user['password'],
                             tenant=user['tenant'])
            self.novaclient.keypairs.create(**keypair)
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

    def create_flavors(self):
        for flavor in self.config.flavors:
            self.novaclient.flavors.create(**flavor)

    def create_vms(self):
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

        def get_parameters_for_vm_creating(_vm):
            return {'image': self.get_image_id(_vm['image']),
                    'flavor': self.get_flavor_id(_vm['flavor']),
                    'nics': get_vm_nics(_vm),
                    'name': _vm['name'],
                    'key_name': _vm.get('key_name')
                    }

        def wait_vm_nic_created(vm_id):
            for i in range(TIMEOUT):
                srv = self.novaclient.servers.get(vm_id)
                if srv.networks:
                    break
            else:
                raise RuntimeError(
                    'NIC for vm with id {0} was not created'.format(vm_id))

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
                    **get_parameters_for_vm_creating(vm))
                vm_ids.append(_vm.id)
                if not vm.get('fip'):
                    continue
                wait_vm_nic_created(_vm.id)
                fip = self.neutronclient.create_floatingip(
                    {"floatingip": {"floating_network_id": self.ext_net_id}})
                _vm.add_floating_ip(fip['floatingip']['floating_ip_address'])
            return vm_ids

        @retry_until_resources_created('vm')
        def wait_until_vms_created(vm_list):
            for vm in vm_list[:]:
                if self.check_vm_state(vm):
                    vms.remove(vm)
            return vms

        vms = create_vms(self.config.vms)
        for tenant, user in zip(self.config.tenants, self.config.users):
            if not tenant.get('vms'):
                continue
            self.switch_user(user=user['name'], password=user['password'],
                             tenant=tenant['name'])
            vms.extend(create_vms(tenant['vms']))
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

    def create_networks(self, network_list, subnet_list):
        ext_router_id = self.get_router_id('ext_router')
        for network, subnet in zip(network_list, subnet_list):
            if network.get('router:external'):
                continue
            net = self.neutronclient.create_network({'network': network})
            subnet['network_id'] = net['network']['id']
            subnet = self.neutronclient.create_subnet({'subnet': subnet})
            self.neutronclient.create_port(
                {"port": {"network_id": net['network']['id']}})
            self.neutronclient.add_interface_router(
                ext_router_id, {"subnet_id": subnet['subnet']['id']})

    def create_router(self, router_list):
        for router in router_list:
            router['router']['external_gateway_info']['network_id'] = \
                self.get_net_id(
                    router['router']['external_gateway_info']['network_id'])
            self.neutronclient.create_router(router)

    def create_external_network(self):
        for network in self.config.networks:
            if network.get('router:external'):
                net = self.neutronclient.create_network({'network': network})
                break
        else:
            raise RuntimeError('Please specify external network in config.py')
        for subnet in self.config.subnets:
            if subnet.get('name') == 'external_subnet':
                subnet['network_id'] = net['network']['id']
                self.neutronclient.create_subnet({'subnet': subnet})
                break
        else:
            raise RuntimeError('Please specify subnet for external network in '
                               'config.py (make sure subnet has field '
                               '"name": "external_subnet").')
        return net['network']['id']

    def create_all_networking(self):
        self.ext_net_id = self.create_external_network()
        self.create_router(self.config.routers)
        self.create_networks(self.config.networks, self.config.subnets)
        for tenant in self.config.tenants:
            if tenant.get('networks'):
                self.switch_user(user=self.username, password=self.password,
                                 tenant=tenant['name'])
                self.create_networks(tenant['networks'], tenant['subnets'])
            if tenant.get('unassociated_fip'):
                for i in range(tenant['unassociated_fip']):
                    self.neutronclient.create_floatingip(
                        {"floatingip": {"floating_network_id": self.ext_net_id}
                         })
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

        vlm_ids = []
        for volume in volumes_list:
            if 'user' in volume:
                user = [u for u in self.config.users
                        if u['name'] == volume['user']][0]
                self.switch_user(user=user['name'], password=user['password'],
                                 tenant=user['tenant'])
            vlm = self.cinderclient.volumes.create(display_name=volume['name'],
                                                   size=volume['size'])
            vlm_ids.append(vlm.id)
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)
        wait_for_volumes(vlm_ids)
        vlm_ids = []
        for volume in volumes_list:
            if 'server_to_attach' not in volume:
                continue
            vlm_id = self.get_volume_id(volume['name'])
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
        dst_cloud = Prerequisites(cloud_prefix='DST', config=self.config)
        for t in self.config.tenants:
            if 'deleted' in t and not t['deleted'] and t['enabled']:
                dst_cloud.keystoneclient.tenants.create(
                    tenant_name=t['name'], description=t['description'],
                    enabled=t['enabled'])

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
        print('>>> Delete tenants which should be deleted:')
        self.delete_tenants()
        print('>>> Create tenant on dst, without security group')
        self.create_tenant_wo_sec_group_on_dst()

    def clean_objects(self):
        def clean_router_ports(router_id):
            subnets = self.neutronclient.list_subnets()
            for subnet in subnets['subnets']:
                try:
                    self.neutronclient.remove_interface_router(
                        router_id, {'subnet_id': subnet['id']})
                except NeutronClientException:
                    pass

        def delete_user_keypairs(_user):
            if not _user.get('enabled'):
                return
            try:
                self.switch_user(user=_user['name'],
                                 password=_user['password'],
                                 tenant=_user['tenant'])
            except Unauthorized:
                return

            keypairs = [k.id for k in self.novaclient.keypairs.list()]
            if keypairs:
                map(self.novaclient.keypairs.delete, keypairs)
            self.switch_user(user=self.username, password=self.password,
                             tenant=self.tenant)

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
                    except NotFound:
                        pass
                else:
                    break
            else:
                raise RuntimeError('Next vms were not deleted')

        for flavor in self.config.flavors:
            try:
                self.novaclient.flavors.delete(
                    self.get_flavor_id(flavor['name']))
            except Exception as e:
                print "Flavor %s failed to delete: %s" % (flavor['name'],
                                                          repr(e))
        vms = self.config.vms
        vms += itertools.chain(*[tenant['vms'] for tenant
                                 in self.config.tenants if tenant.get('vms')])
        for vm in vms:
            try:
                self.novaclient.servers.delete(self.get_vm_id(vm['name']))
            except Exception as e:
                print "VM %s failed to delete: %s" % (vm['name'], repr(e))
        wait_until_vms_all_deleted()
        images = self.config.images
        images += itertools.chain(*[tenant['images'] for tenant
                                  in self.config.tenants
                                  if tenant.get('images')])
        for image in images:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(image['name']))
            except Exception as e:
                print "Image %s failed to delete: %s" % (image['name'],
                                                         repr(e))
        nets = self.config.networks
        nets += itertools.chain(*[tenant['networks'] for tenant
                                  in self.config.tenants
                                  if tenant.get('networks')])
        floatingips = self.neutronclient.list_floatingips()['floatingips']
        for ip in floatingips:
            try:
                self.neutronclient.delete_floatingip(ip['id'])
            except Exception as e:
                print "Ip %s failed to delete: %s" % (
                    ip['floating_ip_address'], repr(e))

        for router in self.config.routers:
            try:
                clean_router_ports(self.get_router_id(
                    router['router']['name']))
                self.neutronclient.delete_router(self.get_router_id(
                    router['router']['name']))
            except Exception as e:
                print "Router failed to delete: %s" % repr(e)

        ports = self.neutronclient.list_ports()['ports']
        ports = [port for port in ports[:]
                 if port['device_owner'] == 'network:dhcp'
                 or not port['device_owner']]

        for port in ports:
            self.neutronclient.delete_port(port['id'])
        for network in nets:
            try:
                self.neutronclient.delete_network(self.get_net_id(
                    network['name']))
            except Exception as e:
                print "Network %s failed to delete: %s" % (network['name'],
                                                           repr(e))
        for snapshot in self.config.snapshots:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(snapshot['image_name']))
            except Exception as e:
                print "Image %s failed to delete: %s" % (
                    snapshot['image_name'], repr(e))

        sgs = self.neutronclient.list_security_groups()['security_groups']
        for sg in sgs:
            try:
                print "delete sg {}".format(sg['name'])
                self.neutronclient.delete_security_group(self.get_sg_id(
                                                         sg['name']))
            except NeutronClientException as e:
                print "Security group %s failed to delete: %s" % (sg['name'],
                                                                  repr(e))
        for user in self.config.users:
            delete_user_keypairs(user)
            try:
                self.keystoneclient.users.delete(
                    self.get_user_id(user['name']))
            except Exception as e:
                print "User %s failed to delete: %s" % (user['name'], repr(e))
        for role in self.config.roles:
            try:
                self.keystoneclient.roles.delete(self.get_role_id(
                    role['name']))
            except Exception as e:
                print "Role %s failed to delete: %s" % (role['name'], repr(e))
        snapshots = self.config.cinder_snapshots
        snapshots += itertools.chain(
            *[tenant['cinder_snapshots'] for tenant in self.config.tenants
              if 'cinder_snapshots' in tenant])
        for snapshot in snapshots:
            try:
                self.cinderclient.volume_snapshots.delete(
                    self.get_volume_snapshot_id(snapshot['display_name']))
            except Exception as e:
                print "Snapshot %s failed to delete: %s" % (
                    snapshot['display_name'], repr(e))

        for tenant in self.config.tenants:
            try:
                self.keystoneclient.tenants.delete(
                    self.get_tenant_id(tenant['name']))
            except Exception as e:
                print "Tenant %s failed to delete: %s" % (tenant['name'],
                                                          repr(e))
        volumes = self.config.cinder_volumes
        volumes += itertools.chain(*[tenant['cinder_volumes'] for tenant
                                     in self.config.tenants if 'cinder_volumes'
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
                                        'self.config.ini', action='store_true')
    parser.add_argument('--env', default='SRC',
                        help='choose cloud: SRC or DST')
    args = parser.parse_args()
    preqs = Prerequisites(config=conf, cloud_prefix=args.env)
    if args.clean:
        preqs.clean_objects()
    else:
        preqs.run_preparation_scenario()
