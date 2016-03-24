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

import json
import os
import unittest

from nose.plugins.attrib import attr

from cloudferry_devlab.tests import config
from cloudferry_devlab.tests import functional_test


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
        for s_vm in src_vms:
            for d_vm in dst_vms:
                if s_vm.name == d_vm.name:
                    self.src_dst_vms.append({
                        'src_vm': s_vm,
                        'dst_vm': d_vm,
                    })

        file_path = os.path.join(self.cloudferry_dir,
                                 config.pre_migration_vm_states_file)
        with open(file_path) as data_file:
            self.original_states = json.load(data_file)

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
                    self.original_states[vm_obj.name],
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
        for vms in self.src_dst_vms:
            dst_vm = vms['dst_vm']
            src_vm = vms['src_vm']
            if self.original_states[src_vm.name] == 'ACTIVE' or \
                    self.original_states[src_vm.name] == 'VERIFY_RESIZE':
                self.assertEqual(src_vm.status, 'SHUTOFF')
                self.assertEqual(dst_vm.status, 'ACTIVE')
            else:
                self.assertEqual(src_vm.status, 'SHUTOFF')
                self.assertEqual(dst_vm.status, 'SHUTOFF')

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_cold_migrate_vm_ip(self):
        """Validate VMs were cold migrated with correct IPs."""
        for vms in self.src_dst_vms:
            dst_vm = vms['dst_vm']
            src_vm = vms['src_vm']
            for src_net in src_vm.addresses:
                for src_net_addr, dst_net_addr in zip(src_vm.addresses
                                                      [src_net],
                                                      dst_vm.addresses
                                                      [src_net]):
                    self.assertEqual(src_net_addr['addr'],
                                     dst_net_addr['addr'])

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_cold_migrate_vm_security_groups(self):
        """Validate VMs were cold migrated with correct security groups."""
        for vms in self.src_dst_vms:
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
