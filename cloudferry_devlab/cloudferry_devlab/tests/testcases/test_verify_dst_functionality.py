# Copyright (c) 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

import time

from cinderclient import exceptions as cinder_exceptions
from fabric import api as fabric_api
from keystoneclient import exceptions as ks_exceptions
from neutronclient.common import exceptions as neutron_exceptions
from novaclient import exceptions as nova_exceptions

from cloudferry_devlab.tests import base
import cloudferry_devlab.tests.config as config
from cloudferry_devlab.tests import functional_test

TIMEOUT = 600
TEST_TENANT_NAME = 'tenant4'
TEST_EXT_ROUTER_NAME = 'ext_router'
TEST_VM_NAME = 'VMtoVerifyDstCloudFunc'
DEFAULT_SERVICE_PORT = 22

CINDER_VOLUME_CHK_CMDS = ['mkdir /tmp/test',
                          '/usr/sbin/mkfs.ext2 /dev/vdb',
                          'mount /dev/vdb /tmp/test',
                          'touch /tmp/test/newfile']

CINDER_VOLUME_PARAMS = {'display_name': 'tn4_volume5',
                        'size': 1,
                        'server_to_attach': None,
                        'device': '/dev/vdb'}
SSH_CHECK_CMD = 'pwd'
SECURITY_GROUP_NAME = 'sg41'


class VerifyDstCloudFunctionality(functional_test.FunctionalTest):

    def setUp(self):
        super(VerifyDstCloudFunctionality, self).setUp()
        self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                   password=self.dst_cloud.password,
                                   tenant=self.dst_cloud.tenant)

        # some initial variables needed for teardown
        self.keypair_list_to_delete = []

        self.dst_tenant_id = self.dst_cloud.get_tenant_id(TEST_TENANT_NAME)

        try:
            # add admin role for the dst admin accout for test tenant
            self.dst_cloud.keystoneclient.roles.add_user_role(
                self.dst_cloud.get_user_id(self.dst_cloud.username),
                self.dst_cloud.get_role_id('admin'),
                self.dst_tenant_id)
        except ks_exceptions.Conflict:
            pass

        self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                   password=self.dst_cloud.password,
                                   tenant=TEST_TENANT_NAME)

        # declare vars in case if condition below will not be satisfied
        image_name = ''
        nic_name = ''
        self.external_network_id = None
        self.neutron_float_ip_quota = 0
        # create vm parameters
        flavor_name = config.flavors[0]['name']
        for tenant in config.tenants:
            if tenant['name'] == TEST_TENANT_NAME:
                image_name = tenant['images'][0]['name']
                nic_name = tenant['networks'][0]['name']
                self.neutron_float_ip_quota = \
                    tenant['neutron_quotas'][0]['floatingip']

        # fetch public_key and according keypair from config
        public_key_name = [x['name'] for x in config.keypairs
                           if x['name'] == config.private_key['name']][0]
        key_pair = [keypair for keypair in config.keypairs
                    if keypair['name'] == public_key_name][0]

        # delete user from key_pair
        if 'user' in key_pair:
            del key_pair['user']

        self.release_fips_tenant()

        for router in self.dst_cloud.neutronclient.list_routers().get(
                'routers'):
            if router.get('name') == TEST_EXT_ROUTER_NAME:
                self.external_network_id = router.get('external_gateway_info'
                                                      ).get('network_id')

        try:
            fip = self.dst_cloud.neutronclient.create_floatingip(
                {"floatingip": {"floating_network_id": self.external_network_id
                                }})
        except neutron_exceptions.NeutronClientException as e:
            self.fail("Can't find external network for floating IP: %s" % e)

        self.float_ip_address = fip['floatingip']['floating_ip_address']
        self.float_ip_id = fip['floatingip']['id']

        self.fip_quota_neutron = self.dst_cloud.neutronclient.show_quota(
            self.dst_tenant_id)['quota']['floatingip']

        # get keypair quota for tenant
        self.keypair_quota = self.dst_cloud.novaclient.quotas.get(
            tenant_id=self.dst_tenant_id).key_pairs
        # delete tenant keys if there are any
        for key_p in self.dst_cloud.novaclient.keypairs.list():
            key_p.delete()
        # create new keypair
        self.dst_cloud.novaclient.keypairs.create(**key_pair)

        sec_group = self.create_security_group_and_rules(SECURITY_GROUP_NAME)
        self.TST_IMAGE = {'image': self.dst_cloud.get_image_id(image_name),
                          'flavor': self.dst_cloud.get_flavor_id(flavor_name),
                          'nics': [{"net-id": self.dst_cloud.get_net_id(
                              nic_name)}],
                          'name': self.generate_random_name(TEST_VM_NAME),
                          'key_name': public_key_name,
                          'security_groups': [sec_group['name']]}

    def tearDown(self):

        self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                   password=self.dst_cloud.password,
                                   tenant=TEST_TENANT_NAME)

        cinder_volumes = self.dst_cloud.cinderclient.volumes.list()
        for volume in cinder_volumes:
            try:
                volume.detach()
                volume.delete()
            except cinder_exceptions.ClientException:
                pass

        for server in self.dst_cloud.novaclient.servers.list():
            server.delete()

        for key_p in self.dst_cloud.novaclient.keypairs.list():
            key_p.delete()

        self.dst_cloud.clean_tools.wait_vms_deleted(self.dst_tenant_id)
        self.release_fips_tenant()

        self.update_floatip_neutron_quota(self.fip_quota_neutron,
                                          TEST_TENANT_NAME)

        try:
            # remove admin role of the dst admin account for test tenant
            self.dst_cloud.keystoneclient.roles.remove_user_role(
                self.dst_cloud.get_user_id(self.dst_cloud.username),
                self.dst_cloud.get_role_id('admin'),
                self.dst_tenant_id)
        except ks_exceptions.Conflict:
            pass

    def generate_random_name(self, input_str):
        return input_str + str(time.ctime()).replace(
            ' ', '').replace(':', '_')

    def create_security_group_and_rules(self, sgr_name):
        sec_group_list = self.dst_cloud.neutronclient.list_security_groups()
        sg_new = False
        if not(sgr_name in [i['name'] for i in
                            sec_group_list['security_groups'] if
                            i['tenant_id'] == self.dst_tenant_id]):
            sec_group = self.dst_cloud.novaclient.security_groups.create(
                name=sgr_name,
                description='Allows SSH to VM.')
            self.dst_cloud.create_security_group_rule(
                sec_group['id'], self.dst_tenant_id,
                protocol='tcp', port_range_max=DEFAULT_SERVICE_PORT,
                port_range_min=DEFAULT_SERVICE_PORT, direction='ingress')

            sg_new = True
        else:
            (sec_group,) = [i for i in sec_group_list['security_groups']
                            if i['name'] == sgr_name and
                            i['tenant_id'] == self.dst_tenant_id]

        if not sg_new:
            if not any(d['port_range_max'] == DEFAULT_SERVICE_PORT and
                       d['direction'] == 'ingress'
                       for d in sec_group['security_group_rules']):
                self.dst_cloud.create_security_group_rule(
                    sec_group['id'], self.dst_tenant_id,
                    protocol='tcp', port_range_max=DEFAULT_SERVICE_PORT,
                    port_range_min=DEFAULT_SERVICE_PORT, direction='ingress')

        return sec_group

    def check_vm_state(self, srv_id):
        srv = self.dst_cloud.novaclient.servers.get(srv_id)
        return srv.status == 'ACTIVE'

    def check_vm_ssh_access(self, vm, ip_addr, username, cmd):
        with fabric_api.settings(host_string=ip_addr,
                                 user=username,
                                 key=config.private_key['id_rsa'],
                                 shell=config.ssh_vm_shell,
                                 abort_on_prompts=True,
                                 connection_attempts=3,
                                 disable_known_hosts=True):
            try:
                fabric_api.sudo(cmd, shell=True)
                msg = 'VM {name} with ip {addr} is accessible via ssh'
                return msg.format(name=vm.name, addr=ip_addr), True
            except SystemExit:
                msg = 'VM {name} with ip {addr} is not accessible via ssh'
                return msg.format(name=vm.name, addr=ip_addr), False

    def check_cinder_volume_on_vm(self, vm, ip_addr, username, cmd):
        with fabric_api.settings(host_string=ip_addr,
                                 user=username,
                                 key=config.private_key['id_rsa'],
                                 shell=config.ssh_vm_shell,
                                 abort_on_prompts=True,
                                 connection_attempts=3,
                                 disable_known_hosts=True):
            try:
                for command in cmd:
                    fabric_api.sudo(command, shell=True)
                msg = 'Cinder volume is OK and accessible on' \
                      'VM with name {name} and ip: {addr}'
                return msg.format(name=vm.name, addr=ip_addr), True
            except SystemExit:
                msg = 'Cinder volume access FAIL on' \
                      'VM with name {name} and ip: {addr}'
                return msg.format(name=vm.name, addr=ip_addr), False

    def release_fips_tenant(self):
        fip_tenant_ids = \
            [f['id'] for f in
             self.dst_cloud.neutronclient.list_floatingips(
                 tenant_id=self.dst_tenant_id)['floatingips']]
        for f_id in fip_tenant_ids:
            self.dst_cloud.neutronclient.delete_floatingip(f_id)
            time.sleep(1)

    def update_floatip_neutron_quota(self, quota_value, tenant_name):
        try:
            self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                       password=self.dst_cloud.password,
                                       tenant=self.dst_cloud.tenant)
            self.dst_cloud.neutronclient.update_quota(
                self.dst_tenant_id, {'quota': {'floatingip': quota_value}})
        finally:
            self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                       password=self.dst_cloud.password,
                                       tenant=tenant_name)

    def wait_service_on_vm_to_be_ready(self, timeout, float_ip, service_port,
                                       vm):
        start_time = time.time()
        end_time = start_time + timeout
        nc_timeout_in_sec = 1
        cmd_ssh_check = "nc -zd -w {0} {1} {2}".format(
            nc_timeout_in_sec,
            float_ip,
            service_port)
        while end_time >= time.time():
            with fabric_api.quiet():
                result = fabric_api.local(cmd_ssh_check,
                                          capture=True).succeeded
            if result:
                return
            time.sleep(1)
        msg = ('Timeout of {tmout} seconds for service port {service_port}'
               ' to be accessible by ip {fip} of vm {vm} with id {vmid}')
        self.fail(msg.format(tmout=timeout, service_port=service_port,
                             fip=float_ip, vm=vm.name, vmid=vm.id))

    def test_cinder_volume(self):
        """Validate destination cloud's volumes running and attaching
        successfully."""
        vm = self.dst_cloud.novaclient.servers.create(**self.TST_IMAGE)
        base.BasePrerequisites.wait_until_objects_created(
            [vm], self.check_vm_state, TIMEOUT)

        vm.add_floating_ip(self.float_ip_address)

        base.BasePrerequisites.wait_until_objects_created(
            [(vm, self.float_ip_address)],
            base.BasePrerequisites.check_floating_ip_assigned, TIMEOUT)
        self.wait_service_on_vm_to_be_ready(TIMEOUT, self.float_ip_address,
                                            DEFAULT_SERVICE_PORT, vm)

        CINDER_VOLUME_PARAMS['server_to_attach'] = vm.name
        self.dst_cloud.create_cinder_volumes([CINDER_VOLUME_PARAMS])

        status_msg, status_state = \
            self.check_cinder_volume_on_vm(
                vm, self.float_ip_address,
                config.ssh_check_user, CINDER_VOLUME_CHK_CMDS)
        if not status_state:
            self.fail(status_msg.format(
                name=vm.name, addr=self.float_ip_address))

    def test_create_vm(self):
        """Validate destination cloud's VMs running successfully."""
        vm = self.dst_cloud.novaclient.servers.create(**self.TST_IMAGE)
        base.BasePrerequisites.wait_until_objects_created(
            [vm], self.check_vm_state, TIMEOUT)

        vm.add_floating_ip(self.float_ip_address)

        base.BasePrerequisites.wait_until_objects_created(
            [(vm, self.float_ip_address)],
            base.BasePrerequisites.check_floating_ip_assigned, TIMEOUT)
        self.wait_service_on_vm_to_be_ready(TIMEOUT, self.float_ip_address,
                                            DEFAULT_SERVICE_PORT, vm)

        status_msg, status_state = self.check_vm_ssh_access(
            vm, self.float_ip_address,
            config.ssh_check_user, SSH_CHECK_CMD)
        if not status_state:
            self.fail(status_msg.format(
                name=vm.name, addr=self.float_ip_address))

    def test_floating_ips_neutron_quota(self):
        """Validate destination cloud's floating IP quota information."""
        self.release_fips_tenant()
        self.update_floatip_neutron_quota(self.neutron_float_ip_quota,
                                          TEST_TENANT_NAME)
        self.release_fips_tenant()

        for _ in xrange(self.neutron_float_ip_quota):
            self.dst_cloud.neutronclient.create_floatingip(
                {"floatingip": {"floating_network_id":
                                self.external_network_id}})
        try:
            self.dst_cloud.neutronclient.create_floatingip(
                {"floatingip": {"floating_network_id":
                                self.external_network_id}})
            # if not Exception, then fip allocated, and it means test fail
            msg = 'Floating IP is allocated over neutron quota limit {0}'
            self.fail(msg.format(self.fip_quota_neutron))
        except neutron_exceptions.NeutronClientException:
            pass

    def test_nova_keypairs_quota_limit(self):
        """Validate destination cloud's keypair quota information."""
        key_pair_test_name = 'TSTSKEYPAIR_QUOTALIM'
        message_out = self.keypair_quota
        quota_limit_left = int(
            self.keypair_quota) - int(
                len(self.dst_cloud.novaclient.keypairs.list()))

        key_pair = config.keypairs[0]
        if 'user' in key_pair:
            del key_pair['user']

        for _ in xrange(quota_limit_left):
            key_pair['name'] = self.generate_random_name(key_pair_test_name)
            self.dst_cloud.novaclient.keypairs.create(**key_pair)
            time.sleep(1)
        try:
            key_pair['name'] = self.generate_random_name(key_pair_test_name)
            self.dst_cloud.novaclient.keypairs.create(**key_pair)
            msg = 'Keypairs quota {0} is NOT reached'
            self.fail(msg.format(message_out))
        except (nova_exceptions.Forbidden, nova_exceptions.OverLimit):
            pass
