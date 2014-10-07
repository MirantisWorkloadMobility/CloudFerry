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


class NeutronNetwork(network.Network):

    """
    The main class for working with Openstack neurton client
    """

    def __init__(self, config):
        self.config = config
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
                    'router_ports': self.get_router_ports(),
                    'floating_ips': self.get_floatingips(),
                    'security_groups': self.get_security_groups()}
        return resource

    def get_networks(self):
        networks = self.neutron_client.list_networks()['networks']
        get_tenant_name = self.__get_tenants_func()
        networks_info = []
        for network in networks:
            net_info = dict()
            net_info['name'] = network['name']
            net_info['admin_state_up'] = network['admin_state_up']
            net_info['shared'] = network['shared']
            net_info['tenant_name'] = get_tenant_name(network['tenant_id'])
            net_info['router:external'] = network['router:external']
            net_info['provider:physical_network'] = network['provider:physical_network']
            net_info['provider:network_type'] = network['provider:network_type']
            net_info['provider:segmentation_id'] = network['provider:segmentation_id']
            networks_info.append(net_info)
        return networks_info

    def get_subnets(self):
        subnets = self.neutron_client.list_subnets()['subnets']
        get_tenant_name = self.__get_tenants_func()
        subnets_info = []
        for subnet in subnets:
            subnet_info = dict()
            subnet_info['name'] = subnet['name']
            subnet_info['enable_dhcp'] = subnet['enable_dhcp']
            subnet_info['allocation_pools'] = subnet['allocation_pools']
            subnet_info['gateway_ip'] = subnet['gateway_ip']
            subnet_info['ip_version'] = subnet['ip_version']
            subnet_info['cidr'] = subnet['cidr']
            subnet_info['network_name'] = self.neutron_client.show_network(subnet['network_id'])['network']['name']
            subnet_info['tenant_name'] = get_tenant_name(subnet['tenant_id'])
            subnets_info.append(subnet_info)
        return subnets_info

    def get_routers(self):
        routers = self.neutron_client.list_routers()['routers']
        get_tenant_name = self.__get_tenants_func()
        routers_info = []
        for router in routers:
            router_info = dict()
            router_info['name'] = router['name']
            router_info['admin_state_up'] = router['admin_state_up']
            router_info['routes'] = router['routes']
            router_info['external_gateway_info'] = router['external_gateway_info']
            if router['external_gateway_info']:
                ext_net = \
                    self.neutron_client.show_network(router['external_gateway_info']['network_id'])['network']
            router_info['ext_net_name'] = ext_net['name']
            router_info['ext_net_tenant_name'] = get_tenant_name(ext_net['tenant_id'])
            router_info['tenant_name'] = get_tenant_name(router['tenant_id'])
            routers_info.append(router_info)
        return routers_info

    def get_router_ports(self):
        ports = self.neutron_client.list_ports()['ports']
        get_tenant_name = self.__get_tenants_func()
        ports_info = []
        for port in filter(lambda p: p['device_owner'] == 'network:router_interface', ports):
            port_info = dict()
            # network_name, mac_address, ip_address, device_owner and admin_state_up
            # are not used. May be these data will be needed in the future
            port_info['network_name'] = self.neutron_client.show_network(port['network_id'])['network']['name']
            port_info['mac_address'] = port['mac_address']
            port_info['subnet_name'] = \
                self.neutron_client.show_subnet(port['fixed_ips'][0]['subnet_id'])['subnet']['name']
            port_info['ip_address'] = port['fixed_ips'][0]['ip_address']
            port_info['router_name'] = self.neutron_client.show_router(port['device_id'])['router']['name']
            port_info['tenant_name'] = get_tenant_name(port['tenant_id'])
            port_info['device_owner'] = port['device_owner']
            port_info['admin_state_up'] = port['admin_state_up']
            ports_info.append(port_info)
        return ports_info

    def get_floatingips(self):
        floatings = self.neutron_client.list_floatingips()['floatingips']
        get_tenant_name = self.__get_tenants_func()
        floatingips_info = []
        for floating in floatings:
            floatingip_info = dict()
            extnet = self.neutron_client.show_network(floating['floating_network_id'])['network']
            floatingip_info['network_name'] = extnet['name']
            floatingip_info['ext_net_tenant_name'] = get_tenant_name(extnet['tenant_id'])
            floatingip_info['tenant_name'] = get_tenant_name(floating['tenant_id'])
            floatingip_info['fixed_ip_address'] = floating['fixed_ip_address']
            floatingip_info['floating_ip_address'] = floating['floating_ip_address']
            floatingips_info.append(floatingip_info)
        return floatingips_info

    def get_security_groups(self):
        return self.neutron_client.list_security_groups()['security_groups']

