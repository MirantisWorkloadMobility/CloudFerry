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
import yaml

import config
from generate_load import Prerequisites
from filtering_utils import FilteringUtils


class DataCollector(object):
    """
    Class to collect data for existing objects on both clusters. As a result
    returns __dict__ with info for both SRC and DST clusters.
    Methods description:
        - unified_method: method to get resources for each tenant separately in
                          case the resource is specific for each tenant, example
                          key-pairs, security-groups, etc.
        - nova_collector: method to get nova resources, list of resources can be
                          obtained in config.py:
                            config.rollback_params['param_dict']['Nova']
        - cinder_collector: method to get cinder resources, list of resources
                            can be obtained in config.py:
                              config.rollback_params['param_dict']['Cinder']
        - glance_collector: method to get glance resources, list of resources
                            can be obtained in config.py:
                              config.rollback_params['param_dict']['Glance']
        - neutron_collector: method to get neutron resources, list of resources
                             can be obtained in config.py:
                               config.rollback_params['param_dict']['Neutron']
        - keystone_collector: method to get keystone resources, list of
                              resources can be obtained in config.py:
                                config.rollback_params['param_dict']['Keystone']
    """
    def __init__(self):
        self.cloud_info = None
        self.migration_utils = FilteringUtils()
        self.main_folder = self.migration_utils.main_folder

    def chose_destination_cloud(self, destination):
        self.cloud_info = Prerequisites(cloud_prefix=destination)

    def return_to_admin_privileges(self):
        self.cloud_info.switch_user(user=self.cloud_info.username,
                                    password=self.cloud_info.password,
                                    tenant=self.cloud_info.tenant)

    def form_client_method(self, *arguments):
        client = self.cloud_info
        for argument in arguments:
            client = getattr(client, argument)
        return client()

    def unified_method(self, destination, collected_items, _res, *args):
        main_dict = {}
        if destination == 'SRC':
            for user, key_pair in zip(config.users, config.keypairs):
                self.cloud_info.switch_user(user=user['name'],
                                            password=user['password'],
                                            tenant=user['tenant'])
                names_list = self.form_client_method(*args)
                instance_list = []
                for instance in names_list:
                    instance_list.append(instance.__dict__['_info'])
                main_dict[user['tenant']] = instance_list
            self.return_to_admin_privileges()
            names_list = self.form_client_method(*args)
            instance_list = []
            for instance in names_list:
                instance_list.append(instance.__dict__['_info'])
            main_dict['admin'] = instance_list
            collected_items[_res] = main_dict
        elif destination == 'DST':
            names_list = self.form_client_method(*args)
            instance_list = []
            for instance in names_list:
                instance_list.append(instance.__dict__['_info'])
            collected_items[_res] = instance_list

    def nova_collector(self, destination, *args):
        """
        Nova data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        for arg in args[0]:
            if arg == 'servers':
                vm_list = []
                servers_list = self.cloud_info.novaclient.servers.list(
                    search_opts={'all_tenants': 1})
                for server in servers_list:
                    vm = server.__dict__
                    vm_list.append(vm['_info'])
                collected_items[arg] = vm_list
            elif arg == 'security_groups':
                self.unified_method(destination, collected_items, arg,
                                    'novaclient', arg, 'list')
            elif arg == 'flavors':
                flavor_list = []
                flavors = self.cloud_info.novaclient.flavors.list()
                for inst in flavors:
                    flavor = inst.__dict__
                    flavor_list.append(flavor['_info'])
                collected_items[arg] = flavor_list
            elif arg == 'quotas':
                quotas = {}
                tenant_list = self.cloud_info.keystoneclient.tenants.list()
                for tenant in tenant_list:
                    tenant = tenant.__dict__
                    quota_list = self.cloud_info.novaclient.quotas.get(
                        tenant['id'])
                    quotas[tenant['name']] = quota_list.__dict__['_info']
                collected_items[arg] = quotas
            elif arg == 'keypairs':
                self.unified_method(destination, collected_items, arg,
                                    'novaclient', arg, 'list')
        return collected_items

    def neutron_collector(self, destination,  *args):
        """
        Neutron data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        for arg in args[0]:
            if arg == 'networks':
                networks_list = self.cloud_info.neutronclient.list_networks()
                collected_items['networks'] = networks_list['networks']
            elif arg == 'subnets':
                subnets_list = self.cloud_info.neutronclient.list_subnets()
                collected_items['subnets'] = subnets_list['subnets']
            elif arg == 'routers':
                routers_list = self.cloud_info.neutronclient.list_routers()
                collected_items['routers'] = routers_list['routers']
            elif arg == 'ports':
                ports_list = self.cloud_info.neutronclient.list_ports()
                collected_items['ports'] = ports_list['ports']
            elif arg == 'quotas':
                quotas = {}
                tenant_list = self.cloud_info.keystoneclient.tenants.list()
                for tenant in tenant_list:
                    tenant = tenant.__dict__
                    quota_list = self.cloud_info.neutronclient.show_quota(
                        tenant['id'])
                    quotas[tenant['name']] = quota_list
                collected_items[arg] = quotas
        return collected_items

    def keystone_collector(self, destination, *args):
        """
        Keystone data collector method.
        """
        def optimizer(resource_list):
            final_list = []
            for resource in resource_list:
                final_list.append(resource.__dict__['_info'])
            return final_list

        collected_items = {}
        self.chose_destination_cloud(destination)
        for arg in args[0]:
            if arg == 'users':
                user_list = self.cloud_info.keystoneclient.users.list()
                data_list = optimizer(user_list)
                collected_items[arg] = data_list
            elif arg == 'tenants':
                tenant_list = self.cloud_info.keystoneclient.tenants.list()
                data_list = optimizer(tenant_list)
                collected_items[arg] = data_list
            elif arg == 'roles':
                role_list = self.cloud_info.keystoneclient.roles.list()
                data_list = optimizer(role_list)
                collected_items[arg] = data_list
        return collected_items

    def glance_collector(self, destination, *args):
        """
        Glance data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        for arg in args[0]:
            if arg == 'images':
                image_list = [x.__dict__['_info'] for x in
                              self.cloud_info.glanceclient.images.list()]
                collected_items[arg] = image_list
            elif arg == 'members':
                members = {}
                image_list = [x.__dict__ for x in
                              self.cloud_info.glanceclient.images.list()]
                for image in image_list:
                    member_list = \
                        self.cloud_info.glanceclient.image_members.list(
                            image['id'])
                    final_list = []
                    for member in member_list:
                        final_list.append(member.__dict__['_info'])
                    members[image['name']] = final_list
                collected_items[arg] = members

        return collected_items

    def cinder_collector(self, destination, *args):
        """
        Cinder data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        for arg in args[0]:
            if arg == 'volumes':
                self.unified_method(destination, collected_items, arg,
                                    'cinderclient', arg, 'list')
            elif arg == 'volume_snapshots':
                self.unified_method(destination, collected_items, arg,
                                    'cinderclient', arg, 'list')
            elif arg == 'quotas':
                quotas = {}
                tenant_list = self.cloud_info.keystoneclient.tenants.list()
                for tenant in tenant_list:
                    tenant = tenant.__dict__
                    quota_list = self.cloud_info.cinderclient.quotas.get(
                        tenant['id'])
                    quotas[tenant['name']] = quota_list.__dict__['_info']
                collected_items[arg] = quotas
        return collected_items

    def data_collector(self):
        all_data = {'SRC': {}, 'DST': {}}
        param_dict = config.rollback_params['param_dict']
        for key in all_data.keys():
            for service in param_dict.keys():
                if service == 'Nova':
                    nova_data_list = \
                        self.nova_collector(key, param_dict[service])
                    all_data[key][service] = nova_data_list
                elif service == 'Keystone':
                    keystone_data_list = \
                        self.keystone_collector(key, param_dict[service])
                    all_data[key][service] = keystone_data_list
                elif service == 'Neutron':
                    neutron_data_list = \
                        self.neutron_collector(key, param_dict[service])
                    all_data[key][service] = neutron_data_list
                elif service == 'Cinder':
                    cinder_data_list = \
                        self.cinder_collector(key, param_dict[service])
                    all_data[key][service] = cinder_data_list
                elif service == 'Glance':
                    glance_data_list = \
                        self.glance_collector(key, param_dict[service])
                    all_data[key][service] = glance_data_list
        return all_data

    def dump_data(self,
                  file_name=config.rollback_params['data_file_names']['PRE']):
        path = 'devlab/tests'
        pre_file_path = os.path.join(self.main_folder, path, file_name)
        data = self.data_collector()
        with open(pre_file_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

if __name__ == '__main__':
    rollback = DataCollector()
    rollback.dump_data()
