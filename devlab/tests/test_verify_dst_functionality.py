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

import tests.config as config
import tests.functional_test as functional_test
import time

from fabric.api import sudo, local, settings, quiet
from neutronclient.common.exceptions import NeutronClientException
from novaclient.exceptions import Forbidden, OverLimit
from cinderclient.exceptions import \
    ClientException as CinderClientBaseException
from keystoneclient import exceptions as ks_exceptions

TIMEOUT = 600
TEST_TENANT_NAME = 'tenant4'
TEST_VM_NAME = 'VMtoVerifyDstCloudFunc'

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

        self.external_networks_ids_list = \
            [i['id'] for i in self.dst_cloud.neutronclient.list_networks(
            )['networks'] if i['router:external'] is True]

        fip = self.dst_cloud.neutronclient.create_floatingip(
            {"floatingip": {"floating_network_id":
                            self.external_networks_ids_list[0]}})

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
            except CinderClientBaseException:
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
                protocol='tcp', port_range_max=22,
                port_range_min=22, direction='ingress')

            sg_new = True
        else:
            (sec_group,) = [i for i in sec_group_list['security_groups']
                            if i['name'] == sgr_name and
                            i['tenant_id'] == self.dst_tenant_id]

        if not sg_new:
            if not any(d['port_range_max'] == 22
                       and d['direction'] == 'ingress'
                       for d in sec_group['security_group_rules']):
                self.dst_cloud.create_security_group_rule(
                    sec_group['id'], self.dst_tenant_id,
                    protocol='tcp', port_range_max=22,
                    port_range_min=22, direction='ingress')

        return sec_group

    def check_vm_ssh_access(self, vm, ip_addr, username, cmd):
        with settings(host_string=ip_addr,
                      user=username,
                      key=config.private_key['id_rsa'],
                      shell=config.ssh_vm_shell,
                      abort_on_prompts=True,
                      connection_attempts=3,
                      disable_known_hosts=True):
            try:
                sudo(cmd, shell=True)
                msg = 'VM {name} with ip {addr} is accessible via ssh'
                return msg.format(name=vm.name, addr=ip_addr), True
            except SystemExit:
                msg = 'VM {name} with ip {addr} is not accessible via ssh'
                return msg.format(name=vm.name, addr=ip_addr), False

    def check_cinder_volume_on_vm(self, vm, ip_addr, username, cmd):
        with settings(host_string=ip_addr,
                      user=username,
                      key=config.private_key['id_rsa'],
                      shell=config.ssh_vm_shell,
                      abort_on_prompts=True,
                      connection_attempts=3,
                      disable_known_hosts=True):
            try:
                for command in cmd:
                    sudo(command, shell=True)
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

    def wait_service_on_vm_to_be_ready(self, timeout,
                                       float_ip, service_port):
        start_time = time.time()
        end_time = start_time + timeout
        nc_timeout_in_sec = 1
        cmd_ssh_check = "nc -zd -w {0} {1} {2}".format(
            nc_timeout_in_sec,
            float_ip,
            service_port)
        while end_time >= time.time():
            with quiet():
                result = local(cmd_ssh_check, capture=True).succeeded
            if result:
                return True
            time.sleep(1)
        return False

    def wait_vm_ready(self, srv, timeout):
        start_time = time.time()
        end_time = start_time + timeout
        while end_time >= time.time():
            vm_status = self.dst_cloud.novaclient.servers.get(srv).status
            if vm_status == 'ACTIVE':
                return True
            elif vm_status == 'ERROR':
                return False
            time.sleep(1)
        return False

    def test_cinder_volume(self):
        vm = self.dst_cloud.novaclient.servers.create(**self.TST_IMAGE)
        if not self.wait_vm_ready(vm, TIMEOUT):
            msg = '{tmout} seconds timeout of waiting for VM to be ready ' \
                  'expired or VM is in ERROR state'
            self.fail(msg.format(tmout=TIMEOUT))

        vm.add_floating_ip(self.float_ip_address)
        if not self.wait_service_on_vm_to_be_ready(
                TIMEOUT, self.float_ip_address, 22):
            msg = 'Timeout of {tmout} seconds for service port {service_port}' \
                  ' to be accessible by ip {fip} of vm {vmid}'
            self.fail(msg.format(tmout=TIMEOUT,
                                 service_port=22,
                                 fip=self.float_ip_address,
                                 vmid=vm.id))

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

        vm = self.dst_cloud.novaclient.servers.create(**self.TST_IMAGE)
        if not self.wait_vm_ready(vm, TIMEOUT):
            msg = '{tmout} seconds timeout of waiting for VM to be ready ' \
                  'expired or VM is in ERROR state'
            self.fail(msg.format(tmout=TIMEOUT))

        vm.add_floating_ip(self.float_ip_address)
        if not self.wait_service_on_vm_to_be_ready(
                TIMEOUT, self.float_ip_address, 22):
            msg = 'Timeout of {tmout} seconds for service port {service_port}' \
                  'to be accessible by ip {fip} of vm {vmid}'
            self.fail(msg.format(tmout=TIMEOUT,
                                 service_port=22,
                                 fip=self.float_ip_address,
                                 vmid=vm.id))

        status_msg, status_state = self.check_vm_ssh_access(
            vm, self.float_ip_address,
            config.ssh_check_user, SSH_CHECK_CMD)
        if not status_state:
            self.fail(status_msg.format(
                name=vm.name, addr=self.float_ip_address))

    def test_floating_ips_neutron_quota(self):

        self.release_fips_tenant()
        self.update_floatip_neutron_quota(self.neutron_float_ip_quota,
                                          TEST_TENANT_NAME)
        self.release_fips_tenant()

        for _ in xrange(self.neutron_float_ip_quota):
            self.dst_cloud.neutronclient.create_floatingip(
                {"floatingip": {"floating_network_id":
                                self.external_networks_ids_list[0]}})
        try:
            self.dst_cloud.neutronclient.create_floatingip(
                {"floatingip": {"floating_network_id":
                                self.external_networks_ids_list[0]}})
            # if not Exception, then fip allocated, and it means test fail
            msg = 'Floating IP is allocated over neutron quota limit {0}'
            self.fail(msg.format(self.fip_quota_neutron))
        except NeutronClientException:
            pass

    def test_nova_keypairs_quota_limit(self):
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
        except (Forbidden, OverLimit):
            pass
