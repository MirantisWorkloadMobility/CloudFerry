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

from cloudferrylib.base import network
from neutronclient.v2_0 import client as neutron_client
from neutronclient.common.exceptions import IpAddressGenerationFailureClient
from utils import get_log

LOG = get_log(__name__)
ADMIN_TENANT = 'admin'

class NeutronNetwork(network.Network):

    """
    The main class for working with Openstack neutron client
    """

    def __init__(self, config):
        self.config = config
        # TODO: implement switch to quantumclient if we have quantum-server
        self.neutron_client = self.get_client()
        super(NeutronNetwork, self).__init__()

    def get_client(self):
        return neutron_client.Client(username=self.config["user"],
                                     password=self.config["password"],
                                     tenant_name=self.config["tenant"],
                                     auth_url="http://" + self.config["host"] + ":35357/v2.0/")

    def read_info(self, opts=None):
        opts = {} if not opts else opts
        resource = {'networks': self.get_networks(),
                    'subnets': self.get_subnets(),
                    'routers': self.get_routers(),
                    'floating_ips': self.get_floatingips(),
                    'security_groups': self.get_security_groups()}
        return resource

    def deploy(self, info):
        self.upload_networks(info['networks'])
        self.upload_subnets(info['networks'], info['subnets'])
        self.upload_routers(info['networks'], info['subnets'], info['routers'])
        self.upload_floatingips(info['networks'], info['floating_ips'])

    def get_networks(self):
        networks = self.neutron_client.list_networks()['networks']
        get_tenant_name = self.__get_tenants_func()
        networks_info = []
        for network in networks:
            net_info = dict()
            net_info['name'] = network['name']
            net_info['id'] = network['id']
            net_info['admin_state_up'] = network['admin_state_up']
            net_info['shared'] = network['shared']
            net_info['tenant_id'] = network['tenant_id']
            net_info['tenant_name'] = get_tenant_name(network['tenant_id'])
            net_info['subnet_names'] = \
                [self.neutron_client.show_subnet(snet)['subnet']['name'] for snet in network['subnets']]
            net_info['router:external'] = network['router:external']
            net_info['provider:physical_network'] = network['provider:physical_network']
            net_info['provider:network_type'] = network['provider:network_type']
            net_info['provider:segmentation_id'] = network['provider:segmentation_id']
            net_info['res_hash'] = self.__get_resource_hash(net_info,
                                                            'name',
                                                            'shared',
                                                            'tenant_name',
                                                            'subnet_names',
                                                            'router:external')
            networks_info.append(net_info)
        return networks_info

    def get_subnets(self):
        subnets = self.neutron_client.list_subnets()['subnets']
        get_tenant_name = self.__get_tenants_func()
        subnets_info = []
        for subnet in subnets:
            subnet_info = dict()
            subnet_info['name'] = subnet['name']
            subnet_info['id'] = subnet['id']
            subnet_info['enable_dhcp'] = subnet['enable_dhcp']
            subnet_info['allocation_pools'] = subnet['allocation_pools']
            subnet_info['gateway_ip'] = subnet['gateway_ip']
            subnet_info['ip_version'] = subnet['ip_version']
            subnet_info['cidr'] = subnet['cidr']
            subnet_info['network_name'] = self.neutron_client.show_network(subnet['network_id'])['network']['name']
            subnet_info['network_id'] = subnet['network_id']
            subnet_info['tenant_name'] = get_tenant_name(subnet['tenant_id'])
            subnet_info['res_hash'] = self.__get_resource_hash(subnet_info,
                                                                'name',
                                                                'enable_dhcp',
                                                                'allocation_pools',
                                                                'gateway_ip',
                                                                'cidr',
                                                                'tenant_name')
            subnets_info.append(subnet_info)
        return subnets_info

    def get_routers(self):
        routers = self.neutron_client.list_routers()['routers']
        get_tenant_name = self.__get_tenants_func()
        routers_info = []
        for router in routers:
            router_info = dict()
            router_info['name'] = router['name']
            router_info['id'] = router['id']
            router_info['admin_state_up'] = router['admin_state_up']
            router_info['routes'] = router['routes']
            router_info['external_gateway_info'] = router['external_gateway_info']
            if router['external_gateway_info']:
                ext_net = \
                    self.neutron_client.show_network(router['external_gateway_info']['network_id'])['network']
                router_info['ext_net_name'] = ext_net['name']
                router_info['ext_net_tenant_name'] = get_tenant_name(ext_net['tenant_id'])
                router_info['ext_net_id'] = router['external_gateway_info']['network_id']
            router_info['tenant_name'] = get_tenant_name(router['tenant_id'])
            # we need to get router's fixed ips, because without it we can't exactly determine a router
            router_info['ips'] = list()
            router_info['subnet_ids'] = list()
            for port in self.neutron_client.list_ports()['ports']:
                if port['device_id'] == router['id']:
                    for ip_info in port['fixed_ips']:
                        router_info['ips'].append(ip_info['ip_address'])
                        if ip_info['subnet_id'] not in router_info['subnet_ids']:
                            router_info['subnet_ids'].append(ip_info['subnet_id'])
            router_info['res_hash'] = self.__get_resource_hash(router_info,
                                                               'name',
                                                               'routes',
                                                               'tenant_name')
            routers_info.append(router_info)
        return routers_info

    def get_floatingips(self):
        floatings = self.neutron_client.list_floatingips()['floatingips']
        get_tenant_name = self.__get_tenants_func()
        floatingips_info = []
        for floating in floatings:
            floatingip_info = dict()
            extnet = self.neutron_client.show_network(floating['floating_network_id'])['network']
            floatingip_info['id'] = floating['id']
            floatingip_info['floating_network_id'] = floating['floating_network_id']
            floatingip_info['network_name'] = extnet['name']
            floatingip_info['ext_net_tenant_name'] = get_tenant_name(extnet['tenant_id'])
            floatingip_info['tenant_name'] = get_tenant_name(floating['tenant_id'])
            floatingip_info['fixed_ip_address'] = floating['fixed_ip_address']
            floatingip_info['floating_ip_address'] = floating['floating_ip_address']
            floatingips_info.append(floatingip_info)
        return floatingips_info

    def get_security_groups(self):
        return self.neutron_client.list_security_groups()['security_groups']

    def upload_networks(self, networks):
        existing_nets_hashlist = [ex_net['res_hash'] for ex_net in self.get_networks()]
        for network in networks:
            tenant_id = self.__get_tenant_id_by_name(self.keystone_client, network['tenant_name'])
            network_info = {'network': {'name': network['name'],
                                        'admin_state_up': network['admin_state_up'],
                                        'tenant_id': tenant_id,
                                        'shared': network['shared']}}
            if network['router:external']:
                network_info['network']['router:external'] = network['router:external']
                network_info['network']['provider:physical_network'] = network['provider:physical_network']
                network_info['network']['provider:network_type'] = network['provider:network_type']
                if network['provider:network_type'] == 'vlan':
                    network_info['network']['provider:segmentation_id'] = network['provider:segmentation_id']
            if network['res_hash'] not in existing_nets_hashlist:
                self.neutron_client.create_network(network_info)
            else:
                LOG.info("| Dst cloud already has the same network with name %s in tenant %s" %
                         (network['name'], network['tenant_name']))

    def upload_subnets(self, networks, subnets):
        existing_nets = self.get_networks()
        existing_subnets_hashlist = [ex_snet['res_hash'] for ex_snet in self.get_subnets()]
        for subnet in subnets:
            tenant_id = self.__get_tenant_id_by_name(self.keystone_client, subnet['tenant_name'])
            net_hash = self.__get_resource_hash_by_id(networks, subnet['network_id'])
            network_id = self.__get_existing_resource_by_hash(existing_nets, net_hash)['id']
            subnet_info = {'subnet': {'name': subnet['name'],
                                      'enable_dhcp': subnet['enable_dhcp'],
                                      'network_id': network_id,
                                      'cidr': subnet['cidr'],
                                      'allocation_pools': subnet['allocation_pools'],
                                      'gateway_ip': subnet['gateway_ip'],
                                      'ip_version': subnet['ip_version'],
                                      'tenant_id': tenant_id}}
            if subnet['res_hash'] not in existing_subnets_hashlist:
                self.neutron_client.create_subnet(subnet_info)
            else:
                LOG.info("| Dst cloud already has the same subnetwork with name %s in tenant %s" %
                         (subnet['name'], subnet['tenant_name']))

    def upload_routers(self, networks, subnets, routers):
        existing_nets = self.get_networks()
        existing_subnets = self.get_subnets()
        existing_routers = self.get_routers()
        existing_routers_hashlist = [ex_router['res_hash'] for ex_router in existing_routers]
        for router in routers:
            router_info = {'router': {'name': router['name'],
                                      'tenant_id': tenant_id}}
            tenant_id = self.__get_tenant_id_by_name(self.keystone_client, router['tenant_name'])
            if router['external_gateway_info']:
                ex_net_hash = self.__get_resource_hash(networks, router['ext_net_id'])
                ex_net_id = self.__get_existing_resource_by_hash(existing_nets,ex_net_hash)['id']
                router_info['external_gateway_info'] = dict(network_id=ex_net_id)
            if router['res_hash'] not in existing_routers_hashlist:
                new_router = self.neutron_client.create_router(router_info)['router']
                self.add_router_interfaces(router, new_router, subnets, existing_subnets)
            else:
                existing_router = self.__get_existing_resource_by_hash(existing_routers, router['res_hash'])
                if not set(router['ips']).intersection(existing_router['ips']):
                    new_router = self.neutron_client.create_router(router_info)['router']
                    self.add_router_interfaces(router, new_router, subnets, existing_subnets)
                else:
                    LOG.info("| Dst cloud already has the same router with name %s in tenant %s" %
                             (router['name'], router['tenant_name']))

    def add_router_interfaces(self, src_router, dst_router, src_subnets, dst_subnets):
        for subnet_id in src_router['subnet_ids']:
            subnet_hash = self.__get_resource_hash_by_id(src_subnets, subnet_id)
            existing_subnet_id = self.__get_existing_resource_by_hash(dst_subnets, subnet_hash)
            self.neutron_client.add_interface_router(dst_router['id'],
                                                     {"subnet_id": existing_subnet_id})

    def upload_floatingips(self, networks, src_floats):
        existing_nets = self.get_networks()
        ext_nets_ids = []
        # getting list of external networks with allocated floating ips
        for src_float in src_floats:
            ext_net_hash = self.__get_resource_hash_by_id(networks,
                                                          src_float['floating_network_id'])
            ext_net_id = self.__get_existing_resource_by_hash(existing_nets,
                                                              ext_net_hash)['id']
            if ext_net_id not in ext_nets_ids:
                ext_nets_ids.append(ext_net_id)
                self.__allocate_floatingips(ext_net_id)
        existing_floatingips = self.get_floatingips()
        self.__recreate_floatingips(src_floats, networks,
                                    existing_nets, existing_floatingips)
        self.__delete_redundant_floatingips(src_floats, existing_floatingips)


    def __allocate_floatingips(self, ext_net_id):
        try:
            while True:
                self.neutron_client.create_floatingip({'floatingip': {'floating_network_id': ext_net_id}})
        except IpAddressGenerationFailureClient:
            LOG.info("| Floating IPs were allocated in network %s" % ext_net_id)

    def __recreate_floatingips(self, src_floats, src_nets, existing_nets, existing_floatingips):

        """ We recreate floating ips with the same parameters as on src cloud,
        because we can't determine floating ip address during allocation process. """

        for src_float in src_floats:
            tenant_id = self.get_tenant_id_by_name(self.keystone_client,
                                                   src_float['tenant_name'])
            ext_net_hash = self.__get_resource_hash_by_id(src_nets,
                                                          src_float['floating_network_id'])
            ext_net = self.__get_existing_resource_by_hash(existing_nets,
                                                           ext_net_hash)
            for floating in existing_floatingips:
                if floating['floating_ip_address'] == src_float['floating_ip_address']:
                    if floating['floating_network_id'] == ext_net['id']:
                        if floating['tenant_id'] != tenant_id:
                            self.neutron_client.delete_floatingip(floating['id'])
                            self.neutron_client.create_floatingip({'floatingip':
                                                                       {'floating_network_id': ext_net['id'],
                                                                        'tenant_id': tenant_id}})

    def __delete_redundant_floatingips(self, src_floats, existing_floatingips):
        src_floatingips = [src_float['floating_ip_address'] for src_float in src_floats]
        for floatingip in existing_floatingips:
            if floatingip['floating_ip_address'] not in src_floatingips:
                self.neutron_client.delete_floatingip(floatingip['id'])

    def __get_existing_resource_by_hash(self, existing_resources, resource_hash):
        for resource in existing_resources:
            if resource['res_hash'] == resource_hash:
                return resource

    def __get_resource_hash_by_id(self, resources, resource_id):
        for resource in resources:
            if resource['id'] == resource_id:
                return resource['res_hash']

    def __get_resource_hash(self, neutron_resource, *args):
        hash_list = list()
        for arg in args:
            if type(neutron_resource[arg]) is str:
                hash_list.append(neutron_resource[arg].lower())
            else:
                hash_list.append(neutron_resource[arg])
        hash_list.sort()
        return hash(tuple(hash_list))

    def __get_tenants_func(self):
        tenants = {tenant.id: tenant.name for tenant in self.keystone_client.tenants.list()}
        def f(tenant_id):
            return tenants[tenant_id] if tenant_id in tenants.keys() else ADMIN_TENANT
        return f