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

import ConfigParser
import pkg_resources

import yaml

from cloudferry_devlab.tests import base
import cloudferry_devlab.tests.config as cfg
import cloudferry_devlab.tests.utils as utils


class DataCollector(object):
    """
    Class to collect data for existing objects on both clusters. As a result
    returns __dict__ with info for both SRC and DST clusters.
    Methods description:
        - nova_collector: method to get nova resources, list of resources can
                          be obtained in config.py:
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
    def __init__(self, config):
        self.cloud_info = None
        self.utils = utils.Utils()
        confparser = ConfigParser.ConfigParser()
        confparser.read(config.cloud_ferry_conf)
        self.config_ini = base.get_dict_from_config_file(confparser)
        self.config = config

    def chose_destination_cloud(self, destination):
        self.cloud_info = base.BasePrerequisites(
                cloud_prefix=destination,
                config=self.config,
                configuration_ini=self.config_ini)

    def nova_collector(self, destination, resources):
        """
        Nova data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        if 'servers' in resources:
            vm_list = []
            servers_list = self.cloud_info.novaclient.servers.list(
                search_opts={'all_tenants': 1})
            for server in servers_list:
                vm = server.__dict__['_info']
                vm.pop('updated', None)
                vm_list.append(vm)
            collected_items['servers'] = vm_list
        if 'flavors' in resources:
            flavors = self.cloud_info.novaclient.flavors.list(is_public=None)
            collected_items['flavors'] = [f.__dict__['_info'] for f in flavors]
        if 'quotas' in resources:
            quotas = {}
            for tenant in self.cloud_info.keystoneclient.tenants.list():
                quota_list = self.cloud_info.novaclient.quotas.get(
                    tenant.id)
                quotas[tenant.name] = quota_list.__dict__['_info']
            collected_items['quotas'] = quotas

        if 'security_groups' in resources:
            sgs = self.cloud_info.novaclient.security_groups.list()
            collected_items['security_groups'] = [sg.__dict__['_info']
                                                  for sg in sgs]
        if 'keypairs' in resources:
            def get_user(name):
                for _user in users:
                    if _user['name'] == name:
                        return _user
            keypairs = []
            users = self.config.users
            users.append({'name': self.cloud_info.username,
                          'password': self.cloud_info.password,
                          'tenant': self.cloud_info.tenant})
            user_names = [u['name'] for u in self.config.users]
            existing_tenants = [t.id for t in
                                self.cloud_info.keystoneclient.tenants.list()]
            for user in self.cloud_info.keystoneclient.users.list():
                if user.name not in user_names or\
                        not getattr(user, 'tenantId', None) or\
                        not user.enabled or\
                        user.tenantId not in existing_tenants:
                    continue
                creds = get_user(user.name)
                self.cloud_info.switch_user(user=creds['name'],
                                            password=creds['password'],
                                            tenant=creds['tenant'])
                kps = self.cloud_info.novaclient.keypairs.list()
                if kps:
                    kps = [kp.__dict__['_info'] for kp in kps]
                keypairs.append({user.name: kps})
            collected_items['keypairs'] = keypairs
            self.cloud_info.switch_user(user=self.cloud_info.username,
                                        password=self.cloud_info.password,
                                        tenant=self.cloud_info.tenant)
        return collected_items

    def neutron_collector(self, destination, resources):
        """
        Neutron data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        if 'networks' in resources:
            networks_list = self.cloud_info.neutronclient.list_networks()
            collected_items['networks'] = networks_list['networks']
        if 'subnets' in resources:
            subnets_list = self.cloud_info.neutronclient.list_subnets()
            collected_items['subnets'] = subnets_list['subnets']
        if 'routers' in resources:
            routers_list = self.cloud_info.neutronclient.list_routers()
            collected_items['routers'] = routers_list['routers']
        if 'ports' in resources:
            ports_list = self.cloud_info.neutronclient.list_ports()
            collected_items['ports'] = ports_list['ports']
        if 'quotas' in resources:
            quotas = {}
            tenant_list = self.cloud_info.keystoneclient.tenants.list()
            for tenant in tenant_list:
                quota_list = self.cloud_info.neutronclient.show_quota(
                    tenant.id)
                quotas[tenant.name] = quota_list
            collected_items['quotas'] = quotas
        return collected_items

    def keystone_collector(self, destination, resources):
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
        if 'users' in resources:
            user_list = self.cloud_info.keystoneclient.users.list()
            collected_items['users'] = optimizer(user_list)
        if 'tenants' in resources:
            tenant_list = self.cloud_info.keystoneclient.tenants.list()
            collected_items['tenants'] = optimizer(tenant_list)
        if 'roles' in resources:
            role_list = self.cloud_info.keystoneclient.roles.list()
            collected_items['roles'] = optimizer(role_list)
        return collected_items

    def glance_collector(self, destination, resources):
        """
        Glance data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        image_list = [x for x in self.cloud_info.glanceclient.images.list()]
        if 'images' in resources:
            _image_list = [x.__dict__['_info'] for x in image_list]
            collected_items['images'] = _image_list
        if 'members' in resources:
            members = {}
            for image in image_list:
                member_list = self.cloud_info.glanceclient.image_members.list(
                    image.id)
                members[image.name] = [member.__dict__['_info']
                                       for member in member_list]
            collected_items['members'] = members
        return collected_items

    def cinder_collector(self, destination, resources):
        """
        Cinder data collector method.
        """
        collected_items = {}
        self.chose_destination_cloud(destination)
        if 'volumes' in resources:
            volumes = self.cloud_info.cinderclient.volumes.list(
                search_opts={'all_tenants': 1})
            collected_items['volumes'] = [vol.__dict__['_info']
                                          for vol in volumes]
        if 'volume_snapshots' in resources:
            volumes_snp = self.cloud_info.cinderclient.volume_snapshots.list(
                search_opts={'all_tenants': 1})
            collected_items['volume_snapshots'] = [vol.__dict__['_info']
                                                   for vol in volumes_snp]
        if 'quotas' in resources:
            quotas = {}
            tenant_list = self.cloud_info.keystoneclient.tenants.list()
            for tenant in tenant_list:
                quota_list = self.cloud_info.cinderclient.quotas.get(
                    tenant.id)
                quotas[tenant.name] = quota_list.__dict__['_info']
            collected_items['quotas'] = quotas
        return collected_items

    def data_collector(self):
        all_data = {'SRC': {}, 'DST': {}}
        param_dict = self.config.rollback_params['param_dict']
        for key in all_data:
            all_data[key]['Nova'] = self.nova_collector(
                key, param_dict['Nova'])
            all_data[key]['Keystone'] = self.keystone_collector(
                key, param_dict['Keystone'])
            all_data[key]['Neutron'] = self.neutron_collector(
                key, param_dict['Neutron'])
            all_data[key]['Cinder'] = self.cinder_collector(
                key, param_dict['Cinder'])
            all_data[key]['Glance'] = self.glance_collector(
                key, param_dict['Glance'])

        return all_data

    def dump_data(self):
        file_name = self.config.rollback_params['data_file_names']['PRE']
        data = self.data_collector()
        with pkg_resources.resource_stream(__name__, file_name) as f:
            yaml.dump(utils.convert(data), f, default_flow_style=False)

if __name__ == '__main__':
    rollback = DataCollector(cfg)
    rollback.dump_data()
