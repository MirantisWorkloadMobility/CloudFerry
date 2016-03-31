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

import logging
import os
import unittest

from keystoneclient import exceptions as ks_exceptions
from testconfig import config as config_ini

import cloudferry_devlab.tests.config as config
from cloudferry_devlab import generate_load
from cloudferry_devlab.tests import test_exceptions
import cloudferry_devlab.tests.utils as utils


def suppress_dependency_logging():
    suppressed_logs = ['iso8601.iso8601',
                       'keystoneclient.session',
                       'neutronclient.client',
                       'requests.packages.urllib3.connectionpool',
                       'glanceclient.common.http',
                       'paramiko.transport']
    for l in suppressed_logs:
        logging.getLogger(l).setLevel(logging.WARNING)


def get_option_from_config_ini(option, section='migrate'):
    return config_ini.get(section, {}).get(option, 'False')


class FunctionalTest(unittest.TestCase):

    def setUp(self):
        super(FunctionalTest, self).setUp()
        suppress_dependency_logging()
        if not config_ini:
            raise test_exceptions.ConfFileError('Configuration file parameter'
                                                ' --tc-file is missing or '
                                                'the file has wrong format')

        self.src_cloud = generate_load.Prerequisites(
                cloud_prefix='SRC',
                configuration_ini=config_ini,
                config=config)
        self.dst_cloud = generate_load.Prerequisites(
                cloud_prefix='DST',
                configuration_ini=config_ini,
                config=config)
        self.migration_utils = utils.MigrationUtils(config)
        self.config_ini_path = config_ini['general']['configuration_ini_path']
        self.cloudferry_dir = config_ini['general']['cloudferry_dir']
        self.filtering_utils = utils.FilteringUtils(
            os.path.join(self.cloudferry_dir, get_option_from_config_ini(
                'filter_path')))

    def filter_networks(self):
        networks = [i['name'] for i in config.networks]
        for i in config.tenants:
            if 'networks' in i and not i.get('deleted'):
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
            if 'networks' not in tenant or tenant.get('deleted'):
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
        for tenant in config.tenants:
            if tenant.get('routers'):
                for router in tenant.get('routers'):
                    routers.append(router['router']['name'])
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
                    if tenant['name'] == user.get('tenant') and
                    user['enabled'] and not user.get('deleted')
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

    def filter_flavors(self, filter_only_private=False):
        flavors = []
        if filter_only_private:
            nova_args = {'is_public': None}
        else:
            nova_args = None
        all_flavors = config.flavors
        for tenant in config.tenants:
            if tenant.get('flavors'):
                all_flavors += [flavor for flavor in tenant['flavors']]
        for flavor in all_flavors:
            if filter_only_private:
                if flavor.get('is_public') is False:
                    flavors.append(flavor['name'])
            elif 'is_public' not in flavor or flavor.get('is_public'):
                flavors.append(flavor['name'])
        return self._get_nova_resources('flavors', flavors, nova_args)

    def filter_keypairs(self):
        return self.src_cloud.get_users_keypairs()

    def filter_security_groups(self):
        sgs = [sg['name'] for i in config.tenants if 'security_groups' in i
               for sg in i['security_groups']]
        return self._get_neutron_resources('security_groups', sgs)

    def filter_images(self, exclude_images_with_fields=None):
        if exclude_images_with_fields is None:
            exclude_images_with_fields = {}

        if exclude_images_with_fields.get('broken') is None:
            exclude_images_with_fields['broken'] = True

        def _image_exclude_filter(images):
            filtered_images_name = []
            for image in images:
                for key, value in exclude_images_with_fields.iteritems():
                    if key in image and image[key] == value:
                        break
                else:
                    filtered_images_name.append(image['name'])
            return filtered_images_name

        all_images = self.migration_utils.get_all_images_from_config()
        filtered_images = _image_exclude_filter(all_images)

        image_list = self.src_cloud.glanceclient.images.list(is_public=None)
        return [i for i in image_list if i.name in filtered_images]

    def filter_volumes(self):
        volumes = config.cinder_volumes
        for tenant in config.tenants:
            if 'cinder_volumes' in tenant and not tenant.get('deleted'):
                volumes.extend(tenant['cinder_volumes'])
        volumes.extend(config.cinder_volumes_from_images)
        volumes_names = [volume.get('display_name') for volume in volumes]
        opts = {'search_opts': {'all_tenants': 1}}
        return [i for i in self.src_cloud.cinderclient.volumes.list(**opts)
                if i.display_name in volumes_names]

    def filter_health_monitors(self):
        hm = self.src_cloud.neutronclient.list_health_monitors()
        final_hm = [m for m in hm['health_monitors']
                    if self.src_cloud.tenant_exists(tenant_id=m['tenant_id'])]
        return {'health_monitors': final_hm}

    def filter_pools(self):
        pools = self.src_cloud.neutronclient.list_pools()['pools']
        final_p = [p for p in pools
                   if self.src_cloud.tenant_exists(tenant_id=p['tenant_id'])]
        return {'pools': final_p}

    def filter_lbaas_members(self):
        members = self.src_cloud.neutronclient.list_members()['members']
        final_m = [m for m in members
                   if self.src_cloud.tenant_exists(tenant_id=m['tenant_id'])]
        return {'members': final_m}

    def filter_vips(self):
        vips = self.src_cloud.neutronclient.list_vips()['vips']
        final_v = [vip for vip in vips
                   if self.src_cloud.tenant_exists(tenant_id=vip['tenant_id'])]
        return {'vips': final_v}

    def _get_neutron_resources(self, res, names):
        _list = getattr(self.src_cloud.neutronclient, 'list_' + res)()
        return {res: [i for i in _list[res] if i['name'] in names]}

    def _get_nova_resources(self, res, names, args=None):
        client = getattr(self.src_cloud.novaclient, res)
        if args:
            return [i for i in client.list(**args) if i.name in names]
        else:
            return [i for i in client.list() if i.name in names]

    def _get_keystone_resources(self, res, names):
        client = getattr(self.src_cloud.keystoneclient, res)
        return [i for i in client.list()
                if i.name in names]

    def get_vms_with_fip_associated(self):
        vms = config.vms
        for tenant in config.tenants:
            if 'vms' in tenant:
                vms.extend(tenant['vms'])
        return [vm['name'] for vm in vms if vm.get('fip')]

    def tenant_exists(self, keystone_client, tenant_id):
        try:
            keystone_client.get(tenant_id)
        except ks_exceptions.NotFound:
            return False
        return True
