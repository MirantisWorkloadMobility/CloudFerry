# Copyright (c) 2014 Mirantis Inc.
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

from novaclient.v1_1 import client as nova_client

from cloudferrylib.base import compute
from utils import forward_agent


DISK = "disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36


class NovaCompute(compute.Compute):
    """The main class for working with Openstack Nova Compute Service. """

    def __init__(self, config, cloud):
        super(NovaCompute, self).__init__()
        self.config = config
        self.cloud = cloud
        self.identity = cloud.identity
        self.mysql_connector = cloud.mysql_connector
        self.nova_client = self.get_nova_client()

    def get_nova_client(self, params=None):
        """Getting nova client. """
        if params is None:
            params = self.config['cloud']

        return nova_client.Client(params['user'], params['password'],
                                  params['tenant'],
                                  "http://%s:35357/v2.0/" % params['host'])

    def read_info(self, **kwargs):
        """
        Read info from cloud

        :param search_opts: Search options to filter out servers (optional).
        """
        search_opts = kwargs.get('search_opts', None)
        info = {'compute': {'keypairs': {},
                            'instances': {},
                            'flavors': {},
                            'user_quotas': [],
                            'project_quotas': []}}

        for keypair in self.get_keypair_list():
            info['compute']['keypairs'][keypair.id] = {
                'keypair': {'name': keypair.name,
                            'public_key': keypair.public_key},
                'meta': {}}

        for instance in self.get_instances_list(search_opts=search_opts):
            security_groups = []
            interfaces = []

            for security_group in instance.security_groups:
                security_groups.append(security_group['name'])

            for interface in self.get_interface_list(instance.id):
                interfaces.append({'port_id': interface.port_id,
                                   'net_id': interface.net_id,
                                   'fixed_ip': None})
            is_ephemeral = self.get_flavor_from_id(instance.flavor['id']).ephemeral > 0
            is_ceph = self.config['cloud']['backend'].lower == 'ceph'
            host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
            if is_ceph:
                host = self.config['cloud']['host']

            ephemeral_path = {
                'path_src': None,
                'path_dst': None,
                'host_src': host}
            if is_ephemeral:
                ephemeral_path['path_src'] = self._get_file_path(instance,
                                                     is_ephemeral,
                                                     is_ceph)
            diff = {
                'path_src': None,
                'path_dst': None,
                'host_src': host
            }
            if instance.image:
                diff['path_src'] = self._get_file_path(instance, False, is_ceph)

            info['compute']['instances'][instance.id] = {
                'instance': {'name': instance.name,
                             'id': instance.id,
                             'tenant_id': instance.tenant_id,
                             'status': instance.status,
                             'flavor_id': instance.flavor['id'],
                             'image_id': instance.image['id'],
                             'key_name': instance.keyname,
                             'availability_zone': instance.availability_zone,
                             'security_groups': security_groups,
                             'volume': None,
                             'interfaces': interfaces,
                             'host': host
                             },
                'ephemeral': ephemeral_path,
                'diff': diff,
                'meta': {}}

        for flavor in self.get_flavor_list():
            info['compute']['flavors'][flavor.id] = {
                'flavor': {'name': flavor.name,
                           'ram': flavor.ram,
                           'vcpus': flavor.vcpus,
                           'disk': flavor.disk,
                           'ephemeral': flavor.ephemeral,
                           'swap': flavor.swap,
                           'rxtx_factor': flavor.rxtx_factor,
                           'is_public': flavor.is_public},
                'meta': {}}

        if self.config['migrate']['migrate_quotas']:
            user_quotas_cmd = "use nova; SELECT user_id, project_id, " \
                              "resource, hard_limit FROM project_user_quotas " \
                              "WHERE deleted = 0"
            for quota in self.mysql_connector.execute(user_quotas_cmd):
                info['compute']['user_quotas'].append(
                    {'quota': {'user_id': quota[0],
                               'project_id': quota[1],
                               'resource': quota[2],
                               'hard_limit': quota[3]},
                     'meta': {}})

            project_quotas_cmd = "use nova; SELECT project_id, resource, " \
                                 "hard_limit FROM quotas WHERE deleted = 0"
            for quota in self.mysql_connector.execute(project_quotas_cmd):
                info['compute']['project_quotas'].append(
                    {'quota': {'project_id': quota[0],
                               'resource': quota[1],
                               'hard_limit': quota[2]},
                     'meta': {}})
        return info

    def deploy(self, info, **kwargs):
        resources_deploy = kwargs.get('resources_deploy', False)
        if resources_deploy:
            self._deploy_keypair(info['compute']['keypair'])
            self._deploy_flavors(info['compute']['flavors'])
            if self.config['migrate']['migrate_quotas']:
                self._deploy_project_quotas(info['compute']['project_quotas'])
                self._deploy_user_quotas(info['compute']['user_quotas'])
        else:
            self._deploy_instances(info['compute']['instances'])

    def _deploy_user_quotas(self, quotas):
        insert_cmd = "use nova;INSERT INTO quotas " \
                     "(user_id, project_id, resource, hard_limit) " \
                     "VALUES ('%s', '%s', '%s', %s)"
        for _quota in quotas:
            quota = _quota['quota']
            meta = _quota['meta']
            self.mysql_connector.execute(insert_cmd % (
                meta['user']['id'], meta['project']['id'], quota['resource'],
                quota['hard_limit']))

    def _deploy_project_quotas(self, quotas):
        insert_cmd = "use nova;INSERT INTO project_user_quotas " \
                     "(project_id, resource, hard_limit) " \
                     "VALUES ('%s', '%s', %s)"
        for _quota in quotas:
            quota = _quota['quota']
            meta = _quota['meta']
            self.mysql_connector.execute(insert_cmd % (
                meta['project']['id'], quota['resource'], quota['hard_limit']))

    def _deploy_keypair(self, keypairs):
        dest_keypairs = [keypair.name for keypair in self.get_keypair_list()]
        for _keypair in keypairs.itervalues():
            keypair = _keypair['keypair']
            if keypair['name'] in dest_keypairs:
                continue
            self.create_keypair(keypair['name'], keypair['public_key'])

    def _deploy_flavors(self, flavors):
        dest_flavors = {flavor.name: flavor.id for flavor in
                        self.get_flavor_list()}
        for _flavor in flavors.itervalues():
            flavor = _flavor['flavor']
            if flavor['name'] in dest_flavors:
                _flavor['meta']['dest_id'] = dest_flavors[flavor['name']]
                continue
            self.create_flavor(name=flavor['name'], ram=flavor['ram'],
                               vcpus=flavor['vcpus'], disk=flavor['disk'],
                               ephemeral=flavor['ephemeral'],
                               swap=flavor['swap'],
                               rxtx_factor=flavor['rxtx_factor'],
                               is_public=flavor['is_public'])

    def _deploy_instances(self, instances):
        nova_tenants_clients = {
            self.config['cloud']['tenant']: self.nova_client}

        params = {'user': self.config['cloud']['user'],
                  'password': self.config['cloud']['password'],
                  'tenant': self.config['cloud']['tenant'],
                  'host': self.config['cloud']['host']}

        for _instance in instances.itervalues():
            tenant_name = _instance['instance']['tenant_name']
            if tenant_name not in nova_tenants_clients:
                params['tenant'] = tenant_name
                nova_tenants_clients[tenant_name] = self.get_nova_client(params)

        for _instance in instances:
            instance = _instance['instance']
            meta = _instance['meta']
            self.nova_client = nova_tenants_clients[instance['tenant_name']]
            _instance['meta']['dest_id'] = self.create_instance(
                name=instance['name'],
                image=meta['image']['id'],
                flavor=meta['flavor']['id'],
                key_name=instance['key_name'],
                availability_zone=instance[
                    'availability_zone'],
                security_groups=instance['security_groups'])

        self.nova_client = nova_tenants_clients[self.config['cloud']['tenant']]

    def create_instance(self, **kwargs):
        return self.nova_client.servers.create(**kwargs).id

    def get_instances_list(self, detailed=True, search_opts=None,
                           marker=None,
                           limit=None):
        return self.nova_client.servers.list(detailed=detailed,
                                             search_opts=search_opts,
                                             marker=marker, limit=limit)

    def get_instance(self, instance_id):
        return self.get_instances_list(search_opts={'id': instance_id})[0]

    def change_status(self, status, instance=None, instance_id=None):
        if instance_id:
            instance = self.get_instance(instance_id)

        status_map = {
            'start': lambda inst: inst.start(),
            'stop': lambda inst: inst.stop(),
            'resume': lambda inst: inst.resume(),
            'paused': lambda inst: inst.pause(),
            'unpaused': lambda inst: inst.unpause(),
            'suspend': lambda inst: inst.suspend()
        }
        if self.get_status(self.nova_client.servers, instance.id).lower() != status:
            status_map[status](instance)
        self.wait_for_status(self.get_instance, instance_id, status)

    def get_flavor_from_id(self, flavor_id):
        return self.nova_client.flavors.get(flavor_id)

    def get_flavor_list(self, **kwargs):
        return self.nova_client.flavors.list(**kwargs)

    def create_flavor(self, **kwargs):
        return self.nova_client.flavors.create(**kwargs)

    def delete_flavor(self, flavor_id):
        self.nova_client.flavors.delete(flavor_id)

    def get_keypair_list(self):
        return self.nova_client.keypairs.list()

    def get_keypair(self, name):
        return self.nova_client.keypairs.get(name)

    def create_keypair(self, name, public_key=None):
        return self.nova_client.keypairs.create(name, public_key)

    def get_interface_list(self, server_id):
        return self.nova_client.servers.interface_list(server_id)

    def interface_attach(self, server_id, port_id, net_id, fixed_ip):
        return self.nova_client.servers.interface_attach(server_id, port_id,
                                                         net_id, fixed_ip)

    def wait_for_status(self, getter, id, status):
        # FIXME(toha) What if it is infinite loop here?
        while getter.get(id).status != status:
            time.sleep(1)

    def get_status(self, getter, id):
        return getter.get(id).status

    def get_networks(self, instance):
        networks = []
        func_mac_address = self.__get_func_mac_address(instance)
        for network in instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': func_mac_address(network[1][0])
            })

        return networks

    def __get_func_mac_address(self, instance):
        list_mac = self.get_mac_addresses(instance)
        return lambda x: next(list_mac)

