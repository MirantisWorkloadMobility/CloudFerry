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

import unittest

from fabric.api import run, settings
from fabric.network import NetworkError
from generator import generator, generate
from nose.plugins.attrib import attr

from cloudferry_devlab.tests import config
from cloudferry_devlab.tests import functional_test
from cloudferry_devlab.tests import test_exceptions


@generator
class VmMigration(functional_test.FunctionalTest):

    def setUp(self):
        super(VmMigration, self).setUp()

        src_vms = self.get_src_vm_objects_specified_in_config()
        if not src_vms:
            self.skipTest("Nothing to migrate - source vm list is empty")

        src_vms = self.filtering_utils\
            .filter_vms_with_filter_config_file(src_vms)[0]
        if not src_vms:
            self.skipTest("Nothing to migrate - check the filter config "
                          "file. Probably in the instances id list in the "
                          "config file is not specified VMs for migration "
                          "or is specified tenant id and VMs that not belong "
                          "to this tenant.")

        src_vms = [vm for vm in src_vms if vm.status != 'ERROR' and
                   self.tenant_exists(self.src_cloud.keystoneclient,
                                      vm.tenant_id)]
        if not src_vms:
            self.fail("All VMs in SRC was in error state or "
                      "VM's tenant in SRC doesn't exist")

        dst_vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        if not dst_vms:
            self.fail("No VM's on destination. Either Migration was not "
                      "successful for resource 'VM' or it was not initiated")

        self.src_dst_vms = []
        self.set_hash_for_vms(src_vms)
        self.set_hash_for_vms(dst_vms)
        for s_vm in src_vms:
            for d_vm in dst_vms:
                if s_vm.vm_hash == d_vm.vm_hash:
                    self.src_dst_vms.append({
                        'src_vm': s_vm,
                        'dst_vm': d_vm,
                    })

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_vms_not_in_filter_stay_active_on_src(self):
        """Validate VMs which not icluded in filter stays active on SRC cloud.
        """
        for vm in config.vms_not_in_filter:
            vm_list = [x for x in self.src_cloud.novaclient.servers.list(
                       search_opts={'all_tenants': 1}) if x.name == vm]

            for vm_obj in vm_list:
                self.assertEqual(
                    vm_obj.status,
                    self.get_vm_original_state(vm_obj.name),
                    msg="Vm %s has wrong state" % vm_obj.name)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_vm_not_in_filter_did_not_migrate(self):
        """Validate VMs not included in filter file weren't migrated."""
        dst_vms = [x.name for x in self.dst_cloud.novaclient.servers.list(
                   search_opts={'all_tenants': 1})]
        for vm in config.vms_not_in_filter:
            msg = 'VM migrated despite that it was '\
                   'not included in filter, VM info: \n{vm}'
            self.assertNotIn(vm, dst_vms, msg=msg.format(vm=vm))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_cold_migrate_vm_state(self):
        """Validate VMs were cold migrated with correct states."""
        msg = "Vm '%s' (%s) on %s has incorrect state '%s', should be '%s'"
        for vms in self.src_dst_vms:
            dst_vm = vms['dst_vm']
            src_vm = vms['src_vm']
            if self.get_vm_original_state(src_vm.name) in ['ACTIVE',
                                                           'VERIFY_RESIZE']:
                self.assertIn(src_vm.status, ['SHUTOFF', 'ACTIVE'],
                              msg=msg % (src_vm.name, src_vm.id, 'SRC',
                                         src_vm.status, ['SHUTOFF', 'ACTIVE']))
                self.assertEqual(dst_vm.status, 'ACTIVE',
                                 msg=msg % (dst_vm.name, dst_vm.id, 'DST',
                                            dst_vm.status, 'ACTIVE'))
            else:
                self.assertEqual(src_vm.status, 'SHUTOFF',
                                 msg=msg % (src_vm.name, src_vm.id, 'SRC',
                                            src_vm.status, 'SHUTOFF'))
                self.assertEqual(dst_vm.status, 'SHUTOFF',
                                 msg=msg % (dst_vm.name, dst_vm.id, 'DST',
                                            dst_vm.status, 'SHUTOFF'))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_cold_migrate_vm_ip(self):
        """Validate VMs were cold migrated with correct IPs."""
        for vms in self.src_dst_vms:
            dst_vm = vms['dst_vm']
            src_vm = vms['src_vm']
            if src_vm.vm_hash == dst_vm.vm_hash:
                for src_net in src_vm.addresses:
                    for src_net_addr, dst_net_addr in zip(
                            src_vm.addresses.get(src_net),
                            dst_vm.addresses.get(src_net)):
                        self.assertEqual(src_net_addr.get('addr'),
                                         dst_net_addr.get('addr'))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_cold_migrate_vm_security_groups(self):
        """Validate VMs were cold migrated with correct security groups."""
        for vms in self.src_dst_vms:
            if not hasattr(vms['dst_vm'], 'security_groups'):
                continue
            dst_sec_group_names = [x['name'] for x in
                                   vms['dst_vm'].security_groups]
            for security_group in vms['src_vm'].security_groups:
                self.assertIn(security_group['name'], dst_sec_group_names)

    @unittest.skip("Temporarily disabled: image's id changes after migrating")
    def test_cold_migrate_vm_image_id(self):
        """Validate VMs were cold migrated with correct image ids."""
        for vms in self.src_dst_vms:
            self.assertEqual(vms['dst_vm'].image['id'],
                             vms['src_vm'].image['id'])

    def test_vms_with_same_ip_did_not_migrate(self):
        """Validate VMs with same ip did not migrated."""
        vm_addrs = []
        for vms in self.src_dst_vms:
            for net in vms['dst_vm'].addresses:
                vm_addrs.extend([(net, ip['addr']) for ip in vms['dst_vm']
                                .addresses[net] if ip['OS-EXT-IPS:type'] ==
                                 'fixed'])
        duplicates = {vm for vm in vm_addrs if vm_addrs.count(vm) > 1}
        if duplicates:
            msg = ('2 or more vms exist on dst in the same net with same ip'
                   ' address: %s')
            self.fail(msg % duplicates)

    @generate('config_drive', 'key_name', 'security_groups', 'metadata')
    def test_migrate_vms_parameters(self, param):
        """Validate VMs were migrated with correct parameters.

        :param name:
        :param config_drive:
        :param key_name:
        :param security_groups:
        :param metadata:"""
        src_vms = self.get_src_vm_objects_specified_in_config()
        dst_vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})

        filtering_data = self.filtering_utils \
            .filter_vms_with_filter_config_file(src_vms)
        src_vms = filtering_data[0]
        src_vms = [vm for vm in src_vms if vm.status != 'ERROR']

        def compare_vm_parameter(param, vm1, vm2):
            vm1_param = getattr(vm1, param, None)
            vm2_param = getattr(vm2, param, None)
            if param == "config_drive" and vm1_param == u'1':
                vm1_param = u'True'
            if vm1_param != vm2_param:
                error_msg = ('Parameter {param} for VM with name '
                             '{name} is different src: {vm1}, dst: {vm2}')
                self.fail(error_msg.format(param=param, name=vm1.name,
                                           vm1=getattr(vm1, param),
                                           vm2=getattr(vm2, param)))

        self.set_hash_for_vms(src_vms)
        self.set_hash_for_vms(dst_vms)
        if not src_vms:
            self.skipTest('Nothing to check - source resources list is empty')
        for src_vm in src_vms:
            for dst_vm in dst_vms:
                if src_vm.vm_hash != dst_vm.vm_hash:
                    continue
                compare_vm_parameter(param, src_vm, dst_vm)
                break
            else:
                msg = 'VM with hash %s was not found on dst'
                self.fail(msg % str(src_vm.vm_hash))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_vms_with_floating(self):
        """Validate VMs were migrated with floating ip assigned."""
        vm_names_with_fip = self.get_vms_with_fip_associated()
        dst_vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        for vm in dst_vms:
            if vm.name not in vm_names_with_fip:
                continue
            for net in vm.addresses.values():
                if [True for addr in net if 'floating' in addr.values()]:
                    break
            else:
                raise RuntimeError('Vm {0} does not have floating ip'.format(
                    vm.name))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_not_valid_vms_did_not_migrate(self):
        """Validate VMs with invalid statuses weren't migrated.
        Invalid VMs have 'broken': True value in :mod:`config.py`
        """
        all_vms = self.migration_utils.get_all_vms_from_config()
        vms = [vm['name'] for vm in all_vms if vm.get('broken')]
        migrated_vms = []
        for vm in vms:
            try:
                self.dst_cloud.get_vm_id(vm)
                migrated_vms.append(vm)
            except test_exceptions.NotFound:
                pass
        if migrated_vms:
            self.fail('Not valid vms %s migrated')

    @attr(migrated_tenant='tenant2')
    def test_ssh_connectivity_by_keypair(self):
        """Validate migrated VMs ssh connectivity by keypairs."""
        vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        for _vm in vms:
            if 'keypair_test' in _vm.name:
                vm = _vm
                break
        else:
            raise RuntimeError(
                'VM for current test was not spawned on dst. Make sure vm with'
                'name keypair_test has been created on src')
        ip_addr = self.migration_utils.get_vm_fip(vm)
        # make sure 22 port in sec group is open
        self.migration_utils.open_ssh_port_secgroup(self.dst_cloud,
                                                    vm.tenant_id)
        # try to connect to vm via key pair
        with settings(host_string=ip_addr, user="root",
                      key=config.private_key['id_rsa'],
                      abort_on_prompts=True, connection_attempts=3,
                      disable_known_hosts=True):
            try:
                run("pwd", shell=False)
            except NetworkError:
                msg = 'VM with name {name} and ip: {addr} is not accessible'
                self.fail(msg.format(name=vm.name, addr=ip_addr))
            except SystemExit:
                msg = 'VM with name {name} and ip: {addr} is not accessible ' \
                      'via key pair'
                self.fail(msg.format(name=vm.name, addr=ip_addr))
