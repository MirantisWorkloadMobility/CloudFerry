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

import os
import re
import unittest

import yaml
from nose.plugins.attrib import attr

import devlab.tests.functional_test as functional_test


class GroupProcedureVerification(functional_test.FunctionalTest):
    """
    Testing class for grouping verification.
    """
    def setUp(self):
        """
        SetUp method.
        """
        super(GroupProcedureVerification, self).setUp()
        self.main_folder = os.path.dirname(os.path.dirname(os.getcwd()))
        # TODO:
        #  Using relative paths is a bad practice, unfortunately this is the
        #  only way at this moment.
        #  Should be fixed by implementing proper package module for Cloud
        #  Ferry.
        self.conf_path = 'devlab/tests'
        self.TENANT_ID_LENGTH = 32
        self.new_file_name = 'test_file.yaml'
        self.post_conf_dict = {}
        self.pre_conf_dict = {}
        self.src_vms = []
        dst_ip = self._get_ip_from_url(self.dst_cloud.auth_url)
        src_ip = self._get_ip_from_url(self.src_cloud.auth_url)
        cmd_no_path = './../../devlab/provision/generate_config.sh' \
                      ' --cloudferry-path {} --destination {} --src-ip {}' \
                      ' --dst-ip {}'
        cmd = cmd_no_path.format(self.main_folder,
                                 os.path.join(self.main_folder,
                                              self.conf_path),
                                 src_ip, dst_ip)
        os.system(cmd)

    def tearDown(self):
        """
        Clean up method.
        """
        cmd_1 = 'rm {}'.format(os.path.join(self.main_folder, 'devlab/tests',
                                            self.new_file_name.lstrip('/')))
        cmd_2 = 'rm {}'.format(os.path.join(self.main_folder,
                                            'vm_groups.yaml'))
        for cmd in [cmd_1, cmd_2]:
            try:
                os.system(cmd)
            except OSError as e:
                print 'Was unable to delete testing files, error output:' \
                      '\n{}'.format(e)

    def _get_ip_from_url(self, url):
        ip_regexp = r'.+(\d{3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).+'
        return re.match(ip_regexp, url).group(1)

    def _prepare_files(self, grouping_by):
        """
        Method for generation of test/configuration files.
        """
        main_folder = self.main_folder

        file_path = 'devlab/tests/groups_example.yaml'
        exmpl_file_path = os.path.join(main_folder, file_path)
        pre_conf = open(exmpl_file_path, 'r')
        self.pre_conf_dict = yaml.load(pre_conf)

        inst_id_list = []
        inst_3 = None
        for key in self.pre_conf_dict.keys():
            if key == 'user_defined_group_1':
                for val in self.pre_conf_dict[key]:
                    for inst in self.src_vms:
                        if inst['name'] == val:
                            inst_id_list.append(inst['id'])
            elif key == 'user_defined_group_2':
                for inst in self.src_vms:
                    if inst['name'] == self.pre_conf_dict[key][0]:
                        inst_3 = inst['id']
        self.pre_conf_dict['group_by'] = [unicode(grouping_by)]
        self.pre_conf_dict['user_defined_group_1'] = inst_id_list
        self.pre_conf_dict['user_defined_group_2'] = [inst_3]
        file_to_write_into = os.path.join(os.getcwd(), self.new_file_name)
        with open(file_to_write_into, 'w') as stream:
            yaml.dump(self.pre_conf_dict, stream, default_flow_style=False)
        fab_path = os.path.join('devlab/tests', self.new_file_name)
        _cmd = 'cd {cf_folder} && fab get_groups:{config_ini},{new_file}'
        cmd = _cmd.format(cf_folder=main_folder, new_file=fab_path,
                          config_ini='devlab/tests/configuration.ini')
        os.system(cmd)
        post_file_path = os.path.join(main_folder, 'vm_groups.yaml')
        post_conf = file(post_file_path, 'r')
        self.post_conf_dict = yaml.load(post_conf)

    def _get_index(self, given_vm_id):
        for index in range(len(self.src_vms)):
            vm_id = self.src_vms[index]['id']
            if vm_id == given_vm_id:
                return index

    def _verify_user_groups(self, group_list, verify_vm_state):
        """
        Method for verification of the user defined groups and verifying
        if VMs in ERROR state were not grouped.
        """
        for group in group_list:
            for vm in self.post_conf_dict[group]:
                self.assertTrue(vm in self.pre_conf_dict[group])
                self.assertEqual(len(self.pre_conf_dict[group]),
                                 len(self.post_conf_dict[group]))
        vm_id_list = []
        if verify_vm_state is True:
            for lists in self.post_conf_dict.values():
                for item in lists:
                    vm_id_list.append(item)
            self.assertEqual(len(set(vm_id_list)), len(self.src_vms))

    def src_vms_info_generator(self, category):
        self.src_vms = [x.__dict__ for x in
                        self.src_cloud.novaclient.servers.list(
                            search_opts={'all_tenants': 1})]
        self._prepare_files(category)

    def network_verification_scenario(self, verify_vm_state=False):
        neutron = self.src_cloud.neutronclient
        for key in self.pre_conf_dict.keys():
            if self.pre_conf_dict[key][0] == 'network':
                user_defined_groups_list = self.pre_conf_dict.keys()
                for group in user_defined_groups_list:
                    if group == 'group_by':
                        user_defined_groups_list.pop(
                            user_defined_groups_list.index(group))
                for network_id in self.post_conf_dict.keys():
                    if network_id not in user_defined_groups_list:
                        for vm in self.post_conf_dict[network_id]:
                            index = self._get_index(vm)
                            network = neutron.show_network(network_id)
                            network_name = network['network']['name']
                            self.assertTrue(network_name in self.src_vms[index]
                                            ['addresses'].keys())
                    else:
                        self._verify_user_groups(user_defined_groups_list,
                                                 verify_vm_state)

    def tenant_verification_scenario(self, verify_vm_state=False):
        for key in self.pre_conf_dict.keys():
            if self.pre_conf_dict[key][0] == 'tenant':
                for tenant in self.post_conf_dict.keys():
                    if len(tenant) == self.TENANT_ID_LENGTH:
                        for vm in self.post_conf_dict[tenant]:
                            index = self._get_index(vm)
                            self.assertEqual(tenant, self.src_vms[index]
                                             ['tenant_id'])
                    else:
                        self._verify_user_groups([tenant], verify_vm_state)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_grouping_by_network(self):
        """Validate grouping were made by network."""
        self.src_vms_info_generator('network')
        self.network_verification_scenario()

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_grouping_by_tenant(self):
        """Validate grouping were made by tenant."""
        self.src_vms_info_generator('tenant')
        self.tenant_verification_scenario()

    @unittest.skip('Grouping procedure is not filtering VMs by state. VMs in '
                   'Error state are being grouped too.')
    def test_verify_vm_status_filtering_during_grouping(self):
        """Validate VMs status were filtered during grouping."""
        self.src_vms_info_generator('tenant')
        self.src_vms = [vm for vm in self.src_vms if vm['status'] != 'ERROR']
        self.network_verification_scenario(verify_vm_state=True)
        self.tenant_verification_scenario(verify_vm_state=True)
