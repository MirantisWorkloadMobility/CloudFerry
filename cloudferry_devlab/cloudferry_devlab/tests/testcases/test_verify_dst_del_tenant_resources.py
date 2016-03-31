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

from nose.plugins.attrib import attr

import cloudferry_devlab.tests.config as config
from cloudferry_devlab.tests import functional_test


class VerifyDstDeletedTenantResources(functional_test.FunctionalTest):

    def setUp(self):
        super(VerifyDstDeletedTenantResources, self).setUp()
        self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                   password=self.dst_cloud.password,
                                   tenant=self.dst_cloud.tenant)

        self.deleted_tenants = \
            [(tenant['name'], tenant) for tenant in config.tenants
             if 'deleted' in tenant and tenant['deleted'] is True]

        self.dst_tenants = \
            {ten.name: ten.id for
             ten in self.dst_cloud.keystoneclient.tenants.list()}

        dst_cinder_volumes = self.dst_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 0})

        self.dst_volumes_admin = \
            {vol.display_name: vol for vol in dst_cinder_volumes}

        self.dst_vm_list = \
            self.dst_cloud.novaclient.servers.list(
                search_opts={'tenant_id': self.dst_tenants[
                    self.dst_cloud.tenant]})

    def _tenant_users_exist_on_dst(self, users_dict_list):
        undeleted_users = []
        dst_users_list = self.dst_cloud.keystoneclient.users.list()

        for src_user_name in [user['name'] for user in users_dict_list]:
            if src_user_name in dst_users_list:
                undeleted_users.append(src_user_name)
        return undeleted_users

    def _net_is_attached_to_vm(self, src_net_name):
        networks_names_lists = [vm.networks.keys() for vm in self.dst_vm_list]
        network_names_list = sum(networks_names_lists, [])
        return src_net_name in network_names_list

    def _tenant_nets_exist_on_dst(self, tenant_networks):
        dst_nets = self.dst_cloud.neutronclient.list_networks(
            all_tenants=False)['networks']
        nets_ids_list = []
        for dst_net in dst_nets:
            for src_net in tenant_networks:
                if dst_net['name'] == src_net['name']:
                    if not self._net_is_attached_to_vm(src_net['name']):
                        nets_ids_list.append(dst_net['id'])
        return nets_ids_list

    def _tenant_vm_exists_on_dst(self, src_vm_list):
        # according to current implementation,all tenant's vms
        # should be moved tothe 'admin' account
        src_vm_names = [vm['name'] for vm in src_vm_list]
        migrated_vm_list = []
        for dst_vm in self.dst_vm_list:
            for src_vm in src_vm_list:
                if src_vm['name'] == dst_vm.name:
                    if self.dst_tenants[self.dst_cloud.tenant] ==\
                            dst_vm.tenant_id:
                        migrated_vm_list.append(dst_vm.name)

        non_migrated_vms = set(src_vm_names) ^ set(migrated_vm_list)
        return non_migrated_vms

    def _volume_is_attached_to_vm(self, vol_obj):
        match_vm_id = 0
        for attached_dev in vol_obj.attachments:
            for dst_vm in self.dst_vm_list:
                if dst_vm.id == attached_dev['server_id']:
                    match_vm_id += 1
        return len(vol_obj.attachments) == match_vm_id

    def _tenant_volumes_exist_on_dst(self, src_volumes_list):
        result_vol_ids = []
        src_vol_list_by_disp_name = [vol['display_name'] for vol in
                                     src_volumes_list]
        for volume_name, volume_obj in self.dst_volumes_admin.iteritems():
            if volume_name in src_vol_list_by_disp_name:
                if not self._volume_is_attached_to_vm(volume_obj):
                    result_vol_ids.append(volume_obj.id)
        return result_vol_ids

    def _get_tenant_users_with_keypair(self, tenant_name):
        user_names_tenant = \
            [user['name'] for user in config.users if
             'tenant' in user and user['tenant'] == tenant_name]
        src_users_with_keypair = [key['user'] for key in config.keypairs]

        return set(src_users_with_keypair).intersection(user_names_tenant)

    @attr(migrated_tenant='tenant2')
    def test_tenant_exists_on_dst(self):
        """Validate deleted tenant weren't migrated."""
        undeleted_tenants = []
        for tenant_name, _ in self.deleted_tenants:
            if tenant_name in self.dst_tenants:
                undeleted_tenants.append(tenant_name)

        if undeleted_tenants:
            msg = 'Tenants {0} exist on destination, but should be deleted!'
            self.fail(msg.format(undeleted_tenants))

    @attr(migrated_tenant='tenant2')
    def test_tenant_users_exist_on_dst(self):
        """Validate users with deleted tenant were migrated successfuly."""
        undeleted_users = []
        for tenant_name, _ in self.deleted_tenants:
            tenant_users_list_src = \
                [user for user in config.users if
                 'tenant' in user and user['tenant'] == tenant_name]

            tenant_users_dst = \
                self._tenant_users_exist_on_dst(tenant_users_list_src)

            if tenant_users_dst:
                undeleted_users.append({tenant_name: tenant_users_dst})

        if undeleted_users:
            msg = 'Tenant\'s users {0} exist on destination,' \
                  ' but should be deleted!'
            self.fail(msg.format(undeleted_users))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_tenant_net_exists_on_dst(self):
        """Validate tenant's networks were migrated successfuly."""
        tenant_nets_ids = []
        for tenant_name, tenant in self.deleted_tenants:
            undeleted_net_ids_list = \
                self._tenant_nets_exist_on_dst(tenant['networks'])
            if undeleted_net_ids_list:
                tenant_nets_ids.append({tenant_name: undeleted_net_ids_list})

        if tenant_nets_ids:
            msg = 'Tenant\'s network {0} exists on destination,' \
                  ' but should be deleted!'
            self.fail(msg.format(tenant_nets_ids))

    @unittest.skip("Disabled: orphan VMs don't migrate because tenant is "
                   "specified in filter.")
    def test_tenant_vm_exists_on_dst(self):
        """Validate deleted tenant's VMs were migrated."""
        tenants_vms = []
        for tenant_name, tenant in self.deleted_tenants:
            non_migrated_vms = self._tenant_vm_exists_on_dst(tenant['vms'])

            if non_migrated_vms:
                tenants_vms.append({tenant_name: non_migrated_vms})

        if tenants_vms:
            msg = 'Tenant\'s vm {0} does not exist on destination,' \
                  ' but should be!'
            self.fail(msg.format(tenants_vms))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_tenants_volumes_on_dst(self):
        """Validate deleted tenant's volumes were migrated."""
        undeleted_volumes = []
        for tenant_name, tenant in self.deleted_tenants:

            tenant_undeleted_volumes = \
                self._tenant_volumes_exist_on_dst(tenant['cinder_volumes'])
            if tenant_undeleted_volumes:
                undeleted_volumes.append(
                    {tenant_name: tenant_undeleted_volumes})

        if undeleted_volumes:
            msg = ("Tenant's cinder volumes with ids {0} exist on "
                   "destination, but should be deleted!")
            self.fail(msg.format(undeleted_volumes))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_tenant_key_exists_on_dst(self):
        """Validate deleted tenant's keypairs were migrated."""
        unused_keypairs = []
        for tenant_name, tenant in self.deleted_tenants:
            migrated_keys = \
                [key['name'] for key in config.keypairs if
                 key['user'] in
                 self._get_tenant_users_with_keypair(tenant_name)]
            keys_list = []
            for dst_vm in self.dst_vm_list:
                for src_vm in tenant['vms']:
                    if dst_vm.name == src_vm['name']:
                        if 'key_name' not in src_vm:
                            continue
                        if dst_vm.key_name not in migrated_keys:
                            keys_list.append(dst_vm.key_name)
            if keys_list:
                unused_keypairs.append({tenant_name: keys_list})

        if unused_keypairs:
            msg = 'Tenant\'s key_pairs {0} exist on destination,' \
                  ' but should be deleted!'
            self.fail(msg.format(unused_keypairs))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_tenant_flavors_exist_on_dst(self):
        """Validate deleted tenant's flavors were migrated."""
        unused_flavors = []
        flvlist = []
        for tenant_name, tenant in self.deleted_tenants:

            dst_flavors_list = [flavor.name for flavor in
                                self.dst_cloud.novaclient.flavors.list()]
            flvlist = []
            for src_vm in tenant['vms']:
                if not src_vm['flavor'] in dst_flavors_list:
                    flvlist.append(src_vm['flavor'])
            if flvlist:
                unused_flavors.append({tenant_name: flvlist})

        if unused_flavors:
            msg = 'Tenant\'s flavors {0} do not exist on destination,' \
                  ' but should be!'
            self.fail(msg.format(flvlist))

    @unittest.skip("Disabled: orphan subnets don't migrate because tenant is "
                   "specified in filter.")
    def test_subnets_exist_on_dst(self):
        """Validate deleted tenant's subnets were migrated."""
        tenants_subnets = []
        for tenant_name, tenant in self.deleted_tenants:
            all_subnets = self.dst_cloud.neutronclient.list_subnets()

            dst_admin_subnets = \
                [subnet for subnet in all_subnets['subnets'] if
                 subnet['tenant_id'] ==
                 self.dst_tenants[self.dst_cloud.tenant]]

            net_list = []

            for network in tenant['networks']:
                net_list.append(network['subnets'])
            src_tenant_subnets_list = sum(net_list, [])

            migrated_subnets = []
            for src_subnet in src_tenant_subnets_list:
                for dst_subnet in dst_admin_subnets:
                    if src_subnet['name'] == dst_subnet['name']:
                        migrated_subnets.append(src_subnet['name'])

            src_tenant_net_names = [subnet['name'] for
                                    subnet in src_tenant_subnets_list]

            non_migrated_subnets = set(
                src_tenant_net_names) ^ set(migrated_subnets)

            if non_migrated_subnets:
                tenants_subnets.append({tenant_name: non_migrated_subnets})

        if tenants_subnets:
            msg = 'Tenant\'s subnets do not exist on destination,' \
                  ' but should be!'
            self.fail(msg.format(tenants_subnets))
