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
from cloudferrylib.utils import utils as utl
import copy
from cloudferrylib.utils import timeout_exception

DISK = "disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36
INTERFACES = "interfaces"


class NovaCompute(compute.Compute):
    """The main class for working with Openstack Nova Compute Service. """

    def __init__(self, config, cloud):
        super(NovaCompute, self).__init__()
        self.config = config
        self.cloud = cloud
        self.identity = cloud.resources['identity']
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
        get_tenant_name = self.identity.get_tenants_func()

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

            interfaces = self.get_networks(instance)

            is_ephemeral = self.get_flavor_from_id(instance.flavor['id']).ephemeral > 0
            is_ceph = self.config['compute']['backend'].lower() == 'ceph'
            host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
            if is_ceph:
                host = self.config['cloud']['host']

            instance_block_info = utl.get_libvirt_block_info(
                getattr(instance, "OS-EXT-SRV-ATTR:instance_name"),
                self.config['cloud']['host'],
                getattr(instance, 'OS-EXT-SRV-ATTR:host'))

            ephemeral_path = {
                'path_src': None,
                'path_dst': None,
                'host_src': host,
                'host_dst': None}

            if is_ephemeral:
                ephemeral_path['path_src'] = utl.get_disk_path(
                    instance,
                    is_ceph_ephemeral=is_ceph,
                    disk=DISK+LOCAL)
            diff = {
                'path_src': None,
                'path_dst': None,
                'host_src': host,
                'host_dst': None
            }
            if instance.image:
                diff['path_src'] = utl.get_disk_path(
                    instance,
                    instance_block_info,
                    is_ceph_ephemeral=is_ceph)

            info['compute']['instances'][instance.id] = {
                'instance': {'name': instance.name,
                             'id': instance.id,
                             'tenant_id': instance.tenant_id,
                             'tenant_name': get_tenant_name(instance.tenant_id),
                             'status': instance.status,
                             'flavor_id': instance.flavor['id'],
                             'image_id': instance.image['id'] if instance.image else None,
                             'key_name': instance.key_name,
                             'availability_zone': getattr(instance, 'OS-EXT-AZ:availability_zone'),
                             'security_groups': security_groups,
                             'volume': None,
                             'interfaces': interfaces,
                             'host': getattr(instance, 'OS-EXT-SRV-ATTR:host'),
                             'is_ephemeral': is_ephemeral,
                             'volumes': [{'id': v.id,
                                          'num_device': i,
                                          'device': v.device}
                                         for i, v in enumerate(
                                     self.nova_client.volumes.get_server_volumes(instance.id))]
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

        info = copy.deepcopy(info)

        resources_deploy = kwargs.get('resources_deploy', False)
        if resources_deploy:
            self._deploy_keypair(info['compute']['keypairs'])
            self._deploy_flavors(info['compute']['flavors'])
            if self.config['migrate']['migrate_quotas']:
                self._deploy_project_quotas(info['compute']['project_quotas'])
                self._deploy_user_quotas(info['compute']['user_quotas'])
        else:
            info = self._deploy_instances(info['compute'])

        return info

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
                # _flavor['meta']['dest_id'] = dest_flavors[flavor['name']]
                _flavor['meta']['id'] = dest_flavors[flavor['name']]
                continue
            _flavor['meta']['id'] = self.create_flavor(name=flavor['name'], ram=flavor['ram'],
                                    vcpus=flavor['vcpus'], disk=flavor['disk'],
                                    ephemeral=flavor['ephemeral'],
                                    swap=flavor['swap'],
                                    rxtx_factor=flavor['rxtx_factor'],
                                    is_public=flavor['is_public'])['flavor']

    def _deploy_instances(self, info_compute):
        new_ids = {}
        nova_tenants_clients = {
            self.config['cloud']['tenant']: self.nova_client}

        params = {'user': self.config['cloud']['user'],
                  'password': self.config['cloud']['password'],
                  'tenant': self.config['cloud']['tenant'],
                  'host': self.config['cloud']['host']}

        for _instance in info_compute['instances'].itervalues():
            tenant_name = _instance['instance']['tenant_name']
            if tenant_name not in nova_tenants_clients:
                params['tenant'] = tenant_name
                nova_tenants_clients[tenant_name] = self.get_nova_client(params)

        for _instance in info_compute['instances'].itervalues():
            instance = _instance['instance']
            meta = _instance['meta']
            self.nova_client = nova_tenants_clients[instance['tenant_name']]
            create_params = {'name': instance['name'],
                             'flavor': instance['flavor_id'],
                             'key_name': instance['key_name'],
                             'availability_zone': instance['availability_zone'],
                             'security_groups': instance['security_groups'],
                             'nics': instance['nics'],
                             'image': instance['image_id']}
            if not instance['image_id']:
                image_id = meta['image']['image']['id']
                create_params["block_device_mapping_v2"] = [{
                    "source_type": "image",
                    "uuid": image_id,
                    "destination_type": "volume",
                    "volume_size": meta['image']['meta']['volume']['size'],
                    "delete_on_termination": True,
                    "boot_index": 0
                }]
                create_params['image'] = None
            new_id = self.create_instance(**create_params)
            new_ids[new_id] = instance['id']
        self.nova_client = nova_tenants_clients[self.config['cloud']['tenant']]
        return new_ids

    def create_instance(self, **kwargs):
        return self.nova_client.servers.create(**kwargs).id

    def get_instances_list(self, detailed=True, search_opts=None,
                           marker=None,
                           limit=None):
        ids = search_opts.get('id', None) if search_opts else None
        if not ids:
            return self.nova_client.servers.list(detailed=detailed,
                                                 search_opts=search_opts,
                                                 marker=marker, limit=limit)
        else:
            if type(ids) is list:
                return [self.nova_client.servers.get(i) for i in ids]
            else:
                return [self.nova_client.servers.get(ids)]

    def get_instance(self, instance_id):
        return self.get_instances_list(search_opts={'id': instance_id})[0]

    def change_status(self, status, instance=None, instance_id=None):
        if instance_id:
            instance = self.nova_client.servers.get(instance_id)
        curr = self.get_status(self.nova_client.servers, instance.id).lower()
        will = status.lower()
        func_restore = {
            'start': lambda instance: instance.start(),
            'stop': lambda instance: instance.stop(),
            'resume': lambda instance: instance.resume(),
            'paused': lambda instance: instance.pause(),
            'unpaused': lambda instance: instance.unpause(),
            'suspend': lambda instance: instance.suspend(),
            'status': lambda status: lambda instance: self.wait_for_status(instance_id,
                                                                           status)
        }
        map_status = {
            'paused': {
                'active': (func_restore['unpaused'],
                           func_restore['status']('active')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff')),
                'suspend': (func_restore['unpaused'],
                            func_restore['status']('active'),
                            func_restore['suspend'],
                            func_restore['status']('suspend'))
            },
            'suspend': {
                'active': (func_restore['resume'],
                           func_restore['status']('active')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff')),
                'paused': (func_restore['resume'],
                           func_restore['status']('active'),
                           func_restore['paused'],
                           func_restore['status']('paused'))
            },
            'active': {
                'paused': (func_restore['paused'],
                           func_restore['status']('paused')),
                'suspend': (func_restore['suspend'],
                            func_restore['status']('suspend')),
                'shutoff': (func_restore['stop'],
                            func_restore['status']('shutoff'))
            },
            'shutoff': {
                'active': (func_restore['start'],
                           func_restore['status']('active')),
                'paused': (func_restore['start'],
                           func_restore['status']('active'),
                           func_restore['paused'],
                           func_restore['status']('paused')),
                'suspend': (func_restore['start'],
                            func_restore['status']('active'),
                            func_restore['suspend'],
                            func_restore['status']('suspend'))
            }
        }
        if curr != will:
            try:
                reduce(lambda res, f: f(instance), map_status[curr][will], None)
            except timeout_exception.TimeoutException as e:
                return e
        else:
            return True

    def wait_for_status(self, id_obj, status, limit_retry=90):
        count = 0
        getter = self.nova_client.servers
        while getter.get(id_obj).status.lower() != status.lower():
            time.sleep(1)
            count += 1
            if count > limit_retry:
                raise timeout_exception.TimeoutException(getter.get(id_obj).status.lower(), status, "Timeout exp")

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

    def get_status(self, getter, id):
        return getter.get(id).status

    def get_networks(self, instance):
        networks = []
        func_mac_address = self.get_func_mac_address(instance)
        for network in instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': func_mac_address(network[1][0])
            })

        return networks

    def get_func_mac_address(self, instance):
        resources = self.cloud.resources
        if 'network' in resources:
            network = resources['network']
            if 'get_func_mac_address' in dir(network):
                return network.get_func_mac_address(instance)
        return self.default_detect_mac(instance)

    def default_detect_mac(self, arg):
        raise NotImplemented("Not implemented yet function for detect mac address")
