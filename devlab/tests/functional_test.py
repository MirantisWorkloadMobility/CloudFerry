# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import config
import logging
import sys
import os
import unittest
from generate_load import Prerequisites
import utils


def get_cf_root_folder():
    return os.path.dirname(os.path.dirname(os.path.split(__file__)[0]))

sys.path.append(get_cf_root_folder())
import cfglib
cfglib.init_config(os.path.join(get_cf_root_folder(), config.cloud_ferry_conf))


def suppress_dependency_logging():
    suppressed_logs = ['iso8601.iso8601',
                       'keystoneclient.session',
                       'neutronclient.client',
                       'requests.packages.urllib3.connectionpool',
                       'glanceclient.common.http',
                       'paramiko.transport']

    for l in suppressed_logs:
        logging.getLogger(l).setLevel(logging.WARNING)


class FunctionalTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(FunctionalTest, self).__init__(*args, **kwargs)
        suppress_dependency_logging()
        self.src_cloud = Prerequisites(cloud_prefix='SRC', config=config)
        self.dst_cloud = Prerequisites(cloud_prefix='DST', config=config)
        self.filtering_utils = utils.FilteringUtils()
        self.migration_utils = utils.MigrationUtils(config)

    def filter_networks(self):
        networks = [i['name'] for i in config.networks]
        for i in config.tenants:
            if 'networks' in i:
                for j in i['networks']:
                    networks.append(j['name'])
        return self._get_neutron_resources('networks', networks)

    def filter_subnets(self):
        subnets = []
        admin_tenant_id = self.src_cloud.get_tenant_id(self.src_cloud.tenant)
        for net in config.networks:
            if not net.get('subnets'):
                continue
            for subnet in net['subnets']:
                subnet['tenant_id'] = admin_tenant_id
                subnets.append(subnet)
        subnets = [i for net in config.networks if net.get('subnets')
                   for i in net['subnets']]
        for tenant in config.tenants:
            if 'networks' not in tenant:
                continue
            for network in tenant['networks']:
                if 'subnets' not in network:
                    continue
                for subnet in network['subnets']:
                    subnet['tenant_id'] = self.src_cloud.get_tenant_id(
                        tenant['name'])
                    subnets.append(subnet)
        env_subnets = self.src_cloud.neutronclient.list_subnets()['subnets']
        filtered_subnets = {'subnets': []}
        for env_subnet in env_subnets:
            for subnet in subnets:
                same_cidr = env_subnet['cidr'] == subnet['cidr']
                same_tenant = env_subnet['tenant_id'] == subnet['tenant_id']
                if same_cidr and same_tenant:
                    filtered_subnets['subnets'].append(env_subnet)
        return filtered_subnets

    def filter_routers(self):
        routers = [i['router']['name'] for i in config.routers]
        return self._get_neutron_resources('routers', routers)

    def filter_floatingips(self):
        # Now we create floating ip, after tenant networks created.
        # Will be fixed with tests for floating ip associating
        def get_fips(_user):
            self.src_cloud.switch_user(user=_user['name'],
                                       tenant=_user['tenant'],
                                       password=_user['password'])
            _client = self.src_cloud.neutronclient
            return [_fip['floating_ip_address']
                    for _fip in _client.list_floatingips()['floatingips']]

        for tenant in config.tenants:
            fips = [fip for user in config.users
                    if tenant['name'] == user.get('tenant') and user['enabled']
                    and not user.get('deleted')
                    for fip in get_fips(user)]
            return set(fips)

    def filter_users(self):
        users = []
        for user in config.users:
            if user.get('deleted'):
                continue
            if self.src_cloud.tenant_exists(user.get('tenant')) or\
                    self.src_cloud.user_has_not_primary_tenants(user['name']):
                users.append(user['name'])
        return self._get_keystone_resources('users', users)

    def filter_tenants(self):
        tenants = [i['name'] for i in config.tenants]
        return self._get_keystone_resources('tenants', tenants)

    def filter_roles(self):
        roles = [i['name'] for i in config.roles]
        return self._get_keystone_resources('roles', roles)

    def filter_vms(self):
        vms = self.migration_utils.get_all_vms_from_config()
        vms_names = [vm['name'] for vm in vms if not vm.get('broken')]
        opts = {'search_opts': {'all_tenants': 1}}
        return [i for i in self.src_cloud.novaclient.servers.list(**opts)
                if i.name in vms_names]

    def filter_flavors(self):
        flavors = [i['name'] for i in config.flavors]
        return self._get_nova_resources('flavors', flavors)

    def filter_keypairs(self):
        return self.src_cloud.get_users_keypairs()

    def filter_security_groups(self):
        sgs = [sg['name'] for i in config.tenants if 'security_groups' in i
               for sg in i['security_groups']]
        return self._get_neutron_resources('security_groups', sgs)

    def filter_images(self):
        images = [i['name'] for i in config.images]
        for tenant in config.tenants:
            if not tenant.get('images'):
                continue
            [images.append(i['name']) for i in tenant['images']]
        return [i for i in self.src_cloud.glanceclient.images.list()
                if i.name in images]

    def filter_volumes(self):
        volumes = config.cinder_volumes
        [volumes.extend(i['cinder_volumes']) for i in config.tenants
         if 'cinder_volumes' in i]
        volumes.extend(config.cinder_volumes_from_images)
        volumes_names = [volume['display_name'] for volume in volumes]
        opts = {'search_opts': {'all_tenants': 1}}
        return [i for i in self.src_cloud.cinderclient.volumes.list(**opts)
                if i.display_name in volumes_names]

    def _get_neutron_resources(self, res, names):
        _list = getattr(self.src_cloud.neutronclient, 'list_' + res)()
        return {res: [i for i in _list[res] if i['name'] in names]}

    def _get_nova_resources(self, res, names):
        client = getattr(self.src_cloud.novaclient, res)
        return [i for i in client.list()
                if i.name in names]

    def _get_keystone_resources(self, res, names):
        client = getattr(self.src_cloud.keystoneclient, res)
        return [i for i in client.list()
                if i.name in names]

    def get_vms_with_fip_associated(self):
        vms = config.vms
        [vms.extend(i['vms']) for i in config.tenants if 'vms' in i]
        return [vm['name'] for vm in vms if vm.get('fip')]
