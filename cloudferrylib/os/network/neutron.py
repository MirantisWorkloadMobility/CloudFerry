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
from cloudferrylib.utils import utils as utl
import ipaddr

LOG = utl.get_log(__name__)
DEFAULT_SECGR = 'default'


class NeutronNetwork(network.Network):

    """
    The main class for working with Openstack neutron client
    """

    def __init__(self, config, cloud):
        self.cloud = cloud
        self.identity_client = cloud.resources['identity']
        # TODO: implement switch to quantumclient if we have quantum-server
        self.neutron_client = self.get_client()
        super(NeutronNetwork, self).__init__(config)

    def get_client(self):
        return neutron_client.Client(
            username=self.config['cloud']["user"],
            password=self.config['cloud']["password"],
            tenant_name=self.config['cloud']["tenant"],
            auth_url="http://" + self.config['cloud']["host"] + ":35357/v2.0/")

    def read_info(self, **kwargs):

        """Get info about neutron resources:
        :rtype: Dictionary with all necessary neutron info
        """
        info = {'networks': self.get_networks(),
                'subnets': self.get_subnets(),
                'routers': self.get_routers(),
                'floating_ips': self.get_floatingips(),
                'security_groups': self.get_sec_gr_and_rules(),
                'meta': {}}
        return info

    def deploy(self, info):
        deploy_info = info
        self.upload_networks(deploy_info['networks'])
        self.upload_subnets(deploy_info['networks'],
                            deploy_info['subnets'])
        self.upload_routers(deploy_info['networks'],
                            deploy_info['subnets'],
                            deploy_info['routers'])
        self.upload_floatingips(deploy_info['networks'],
                                deploy_info['floating_ips'])
        self.upload_neutron_security_groups(deploy_info['security_groups'])
        self.upload_sec_group_rules(deploy_info['security_groups'])

    def get_func_mac_address(self, instance):
        return self.get_mac_by_ip

    def get_mac_by_ip(self, ip_address):
        for port in self.get_list_ports():
            for fixed_ip_info in port['fixed_ips']:
                if fixed_ip_info['ip_address'] == ip_address:
                    return port["mac_address"]

    def get_list_ports(self, **kwargs):
        return self.neutron_client.list_ports(**kwargs)['ports']

    def create_port(self, net_id, mac, ip, tenant_id, keep_ip, sg_ids=None):
        param_create_port = {'network_id': net_id,
                             'mac_address': mac,
                             'tenant_id': tenant_id}
        if sg_ids:
            param_create_port['security_groups'] = sg_ids
        if keep_ip:
            param_create_port['fixed_ips'] = [{"ip_address": ip}]
        return self.neutron_client.create_port({
            'port': param_create_port})['port']

    def delete_port(self, port_id):
        return self.neutron_client.delete_port(port_id)

    def get_security_groups_list(self, **kwargs):
        return self.neutron_client.\
            list_security_groups(**kwargs)['security_groups']

    def get_network(self, network_info, tenant_id, keep_ip=False):
        if keep_ip:
            instance_addr = ipaddr.IPAddress(network_info['ip'])
            for snet in self.neutron_client.list_subnets()['subnets']:
                if snet['tenant_id'] == tenant_id:
                    if ipaddr.IPNetwork(snet['cidr']).Contains(instance_addr):
                        return self.neutron_client.\
                            list_networks(id=snet['network_id'])['networks'][0]
        if 'id' in network_info:
            return self.neutron_client.\
                list_networks(id=network_info['id'])['networks'][0]
        if 'name' in network_info:
            return self.neutron_client.\
                list_networks(name=network_info['name'])['networks'][0]
        else:
            raise Exception("Can't find suitable network")

    def check_existing_port(self, network_id, mac):
        for port in self.get_list_ports(fields=['network_id',
                                                'mac_address', 'id']):
            if (port['network_id'] == network_id) \
                    and (port['mac_address'] == mac):
                return port['id']
        return None

    def get_networks(self):
        networks = self.neutron_client.list_networks()['networks']
        get_tenant_name = self.identity_client.get_tenants_func()
        networks_info = []
        for network in networks:
            net_info = dict()
            net_info['name'] = network['name']
            net_info['id'] = network['id']
            net_info['admin_state_up'] = network['admin_state_up']
            net_info['shared'] = network['shared']
            net_info['tenant_id'] = network['tenant_id']
            net_info['tenant_name'] = get_tenant_name(network['tenant_id'])
            net_info['subnet_names'] = list()
            for snet in network['subnets']:
                name = self.neutron_client.show_subnet(snet)['subnet']['name']
                net_info['subnet_names'].append(name)
            net_info['router:external'] = network['router:external']
            net_info['provider:physical_network'] = \
                network['provider:physical_network']
            net_info['provider:network_type'] = \
                network['provider:network_type']
            net_info['provider:segmentation_id'] = \
                network['provider:segmentation_id']
            net_info['res_hash'] = self.get_resource_hash(net_info,
                                                          'name',
                                                          'shared',
                                                          'tenant_name',
                                                          'router:external')
            net_info['meta'] = dict()
            # 'subnet_names', -- need to exclude this arg
            # from get_resource_hash ,because
            # we can't find network_id on dst cloud if
            # needed network was uploaded without their subnets --
            # res_hash will be different for matching networks
            networks_info.append(net_info)
        return networks_info

    def get_subnets(self):
        subnets = self.neutron_client.list_subnets()['subnets']
        get_tenant_name = self.identity_client.get_tenants_func()
        subnets_info = []
        for snet in subnets:
            snet_info = dict()
            snet_info['name'] = snet['name']
            snet_info['id'] = snet['id']
            snet_info['enable_dhcp'] = snet['enable_dhcp']
            snet_info['allocation_pools'] = snet['allocation_pools']
            snet_info['gateway_ip'] = snet['gateway_ip']
            snet_info['ip_version'] = snet['ip_version']
            snet_info['cidr'] = snet['cidr']
            net = self.neutron_client.show_network(snet['network_id'])
            snet_info['network_name'] = net['network']['name']
            snet_info['network_id'] = snet['network_id']
            snet_info['tenant_name'] = get_tenant_name(snet['tenant_id'])
            snet_info['res_hash'] = self.get_resource_hash(snet_info,
                                                           'name',
                                                           'enable_dhcp',
                                                           'allocation_pools',
                                                           'gateway_ip',
                                                           'cidr',
                                                           'tenant_name')
            snet_info['meta'] = dict()
            subnets_info.append(snet_info)
        return subnets_info

    def get_routers(self):
        routers = self.neutron_client.list_routers()['routers']
        get_tenant_name = self.identity_client.get_tenants_func()
        routers_info = []
        for router in routers:
            rinfo = dict()
            rinfo['name'] = router['name']
            rinfo['id'] = router['id']
            rinfo['admin_state_up'] = router['admin_state_up']
            rinfo['routes'] = router['routes']
            rinfo['external_gateway_info'] = \
                router['external_gateway_info']
            if router['external_gateway_info']:
                ext_id = router['external_gateway_info']['network_id']
                ext_net = self.neutron_client.show_network(ext_id)['network']
                rinfo['ext_net_name'] = ext_net['name']
                rinfo['ext_net_tenant_name'] = \
                    get_tenant_name(ext_net['tenant_id'])
                rinfo['ext_net_id'] = \
                    router['external_gateway_info']['network_id']
            rinfo['tenant_name'] = get_tenant_name(router['tenant_id'])
            # we need to get router's fixed ips, because without it
            # we can't exactly determine a router
            rinfo['ips'] = list()
            rinfo['subnet_ids'] = list()
            for port in self.neutron_client.list_ports()['ports']:
                if port['device_id'] == router['id']:
                    for ip_info in port['fixed_ips']:
                        rinfo['ips'].append(ip_info['ip_address'])
                        if ip_info['subnet_id'] not in rinfo['subnet_ids']:
                            rinfo['subnet_ids'].append(ip_info['subnet_id'])
            rinfo['res_hash'] = self.get_resource_hash(rinfo,
                                                       'name',
                                                       'routes',
                                                       'tenant_name',
                                                       'ips')
            rinfo['meta'] = dict()
            routers_info.append(rinfo)
        return routers_info

    def get_floatingips(self):
        floatings = self.neutron_client.list_floatingips()['floatingips']
        get_tenant_name = self.identity_client.get_tenants_func()
        floatingips_info = []
        for floating in floatings:
            floatingip_info = dict()
            ext_id = floating['floating_network_id']
            extnet = \
                self.neutron_client.show_network(ext_id)['network']
            floatingip_info['id'] = floating['id']
            floatingip_info['tenant_id'] = floating['tenant_id']
            floatingip_info['floating_network_id'] = ext_id
            floatingip_info['network_name'] = extnet['name']
            floatingip_info['ext_net_tenant_name'] = \
                get_tenant_name(extnet['tenant_id'])
            floatingip_info['tenant_name'] = \
                get_tenant_name(floating['tenant_id'])
            floatingip_info['fixed_ip_address'] = floating['fixed_ip_address']
            floatingip_info['floating_ip_address'] = \
                floating['floating_ip_address']
            floatingip_info['meta'] = dict()
            floatingips_info.append(floatingip_info)
        return floatingips_info

    def get_security_groups(self):
        sec_grs = self.neutron_client.list_security_groups()['security_groups']
        return sec_grs

    def get_sec_gr_and_rules(self):
        sec_grs = self.get_security_groups()
        get_tenant_name = self.identity_client.get_tenants_func()
        sec_groups_info = []
        for sec_gr in sec_grs:
            sec_gr_info = dict()
            sec_gr_info['name'] = sec_gr['name']
            sec_gr_info['id'] = sec_gr['id']
            sec_gr_info['tenant_id'] = sec_gr['tenant_id']
            sec_gr_info['tenant_name'] = get_tenant_name(sec_gr['tenant_id'])
            sec_gr_info['description'] = sec_gr['description']
            sec_gr_info['security_group_rules'] = list()
            for rule in sec_gr['security_group_rules']:
                r_info = {'remote_group_id': rule['remote_group_id'],
                          'direction': rule['direction'],
                          'remote_ip_prefix': rule['remote_ip_prefix'],
                          'protocol': rule['protocol'],
                          'port_range_min': rule['port_range_min'],
                          'port_range_max': rule['port_range_max'],
                          'ethertype': rule['ethertype'],
                          'security_group_id': rule['security_group_id'],
                          'rule_hash':
                              self.get_resource_hash(rule,
                                                     'direction',
                                                     'remote_ip_prefix',
                                                     'protocol',
                                                     'port_range_min',
                                                     'port_range_max',
                                                     'ethertype'),
                          'meta': dict()}
                sec_gr_info['security_group_rules'].append(r_info)
            sec_gr_info['res_hash'] = self.get_resource_hash(sec_gr_info,
                                                             'name',
                                                             'tenant_name',
                                                             'description')
            sec_gr_info['meta'] = dict()
            sec_groups_info.append(sec_gr_info)
        return sec_groups_info

    def upload_neutron_security_groups(self, sec_groups):
        exist_secgrs = self.get_sec_gr_and_rules()
        exis_secgrs_hashlist = [ex_sg['res_hash'] for ex_sg in exist_secgrs]
        for sec_group in sec_groups:
            if sec_group['name'] != DEFAULT_SECGR:
                if sec_group['res_hash'] not in exis_secgrs_hashlist:
                    tenant_id = \
                        self.identity_client.get_tenant_id_by_name(
                            sec_group['tenant_name']
                        )
                    sg_info = \
                        {
                            'security_group':
                                {
                                    'name': sec_group['name'],
                                    'tenant_id': tenant_id,
                                    'description': sec_group['description']
                                }
                        }
                    sec_group['meta']['id'] = self.neutron_client.\
                        create_security_group(sg_info)['security_group']['id']

    def upload_sec_group_rules(self, sec_groups):
        ex_secgrs = self.get_sec_gr_and_rules()
        for sec_gr in sec_groups:
            ex_secgr = \
                self.get_res_by_hash(ex_secgrs, sec_gr['res_hash'])
            exrules_hlist = \
                [r['rule_hash'] for r in ex_secgr['security_group_rules']]
            for rule in sec_gr['security_group_rules']:
                if rule['protocol'] \
                        and (rule['rule_hash'] not in exrules_hlist):
                    rinfo = \
                        {'security_group_rule': {
                            'direction': rule['direction'],
                            'protocol': rule['protocol'],
                            'port_range_min': rule['port_range_min'],
                            'port_range_max': rule['port_range_min'],
                            'ethertype': rule['ethertype'],
                            'remote_ip_prefix': rule['remote_ip_prefix'],
                            'security_group_id': ex_secgr['id'],
                            'tenant_id': ex_secgr['tenant_id']}}
                    if rule['remote_group_id']:
                        remote_sghash = \
                            self.get_res_hash_by_id(sec_groups,
                                                    rule['remote_group_id'])
                        rem_ex_sec_gr = \
                            self.get_res_by_hash(ex_secgrs,
                                                 remote_sghash)
                        rinfo['security_group_rule']['remote_group_id'] = \
                            rem_ex_sec_gr['id']
                    new_rule = \
                        self.neutron_client.create_security_group_rule(rinfo)
                    rule['meta']['id'] = new_rule['security_group_rule']['id']

    def upload_networks(self, networks):
        existing_nets_hashlist = \
            [ex_net['res_hash'] for ex_net in self.get_networks()]
        for net in networks:
            tenant_id = \
                self.identity_client.get_tenant_id_by_name(net['tenant_name'])
            network_info = {
                'network':
                    {'name': net['name'],
                     'admin_state_up': net['admin_state_up'],
                     'tenant_id': tenant_id,
                     'shared': net['shared']}
            }
            if net['router:external']:
                network_info['network']['router:external'] = \
                    net['router:external']
                network_info['network']['provider:physical_network'] = \
                    net['provider:physical_network']
                network_info['network']['provider:network_type'] = \
                    net['provider:network_type']
                if net['provider:network_type'] == 'vlan':
                    network_info['network']['provider:segmentation_id'] = \
                        net['provider:segmentation_id']
            if net['res_hash'] not in existing_nets_hashlist:
                net['meta']['id'] = self.neutron_client.\
                    create_network(network_info)['network']['id']
            else:
                LOG.info("| Dst cloud already has the same network "
                         "with name %s in tenant %s" %
                         (net['name'], net['tenant_name']))

    def upload_subnets(self, networks, subnets):
        existing_nets = self.get_networks()
        existing_subnets_hashlist = \
            [ex_snet['res_hash'] for ex_snet in self.get_subnets()]
        for snet in subnets:
            tenant_id = \
                self.identity_client.get_tenant_id_by_name(snet['tenant_name'])
            net_hash = \
                self.get_res_hash_by_id(networks, snet['network_id'])
            network_id = \
                self.get_res_by_hash(existing_nets, net_hash)['id']
            subnet_info = {
                'subnet':
                    {'name': snet['name'],
                     'enable_dhcp': snet['enable_dhcp'],
                     'network_id': network_id,
                     'cidr': snet['cidr'],
                     'allocation_pools': snet['allocation_pools'],
                     'gateway_ip': snet['gateway_ip'],
                     'ip_version': snet['ip_version'],
                     'tenant_id': tenant_id}}
            if snet['res_hash'] not in existing_subnets_hashlist:
                snet['meta']['id'] = self.neutron_client.\
                    create_subnet(subnet_info)['subnet']['id']
            else:
                LOG.info("| Dst cloud already has the same subnetwork "
                         "with name %s in tenant %s" %
                         (snet['name'], snet['tenant_name']))

    def upload_routers(self, networks, subnets, routers):
        existing_nets = self.get_networks()
        existing_subnets = self.get_subnets()
        existing_routers = self.get_routers()
        existing_routers_hashlist = \
            [ex_router['res_hash'] for ex_router in existing_routers]
        for router in routers:
            tname = router['tenant_name']
            tenant_id = \
                self.identity_client.get_tenant_id_by_name(tname)
            r_info = {'router': {'name': router['name'],
                                 'tenant_id': tenant_id}}
            if router['external_gateway_info']:
                ex_net_hash = \
                    self.get_res_hash_by_id(networks, router['ext_net_id'])
                ex_net_id = \
                    self.get_res_by_hash(existing_nets, ex_net_hash)['id']
                r_info['router']['external_gateway_info'] = \
                    dict(network_id=ex_net_id)
            if router['res_hash'] not in existing_routers_hashlist:
                new_router = \
                    self.neutron_client.create_router(r_info)['router']
                router['meta']['id'] = new_router['id']
                self.add_router_interfaces(router,
                                           new_router,
                                           subnets,
                                           existing_subnets)
            else:
                existing_router = self.get_res_by_hash(existing_routers,
                                                       router['res_hash'])
                if not set(router['ips']).intersection(existing_router['ips']):
                    new_router = \
                        self.neutron_client.create_router(r_info)['router']
                    router['meta']['id'] = new_router['id']
                    self.add_router_interfaces(router,
                                               new_router,
                                               subnets,
                                               existing_subnets)
                else:
                    LOG.info("| Dst cloud already has the same router "
                             "with name %s in tenant %s" %
                             (router['name'], router['tenant_name']))

    def add_router_interfaces(self, src_router, dst_router,
                              src_snets, dst_sets):
        for snet_id in src_router['subnet_ids']:
            snet_hash = self.get_res_hash_by_id(src_snets, snet_id)
            ex_snet = self.get_res_by_hash(dst_sets,
                                           snet_hash)
            if dst_router['external_gateway_info']:
                if ex_snet['network_id'] == \
                        dst_router['external_gateway_info']['network_id']:
                    continue
            self.neutron_client.add_interface_router(
                dst_router['id'],
                {"subnet_id": ex_snet['id']})

    def upload_floatingips(self, networks, src_floats):
        existing_nets = self.get_networks()
        ext_nets_ids = []
        # getting list of external networks with allocated floating ips
        for src_float in src_floats:
            ext_net_hash = \
                self.get_res_hash_by_id(networks,
                                        src_float['floating_network_id'])
            ext_net_id = \
                self.get_res_by_hash(existing_nets, ext_net_hash)['id']
            if ext_net_id not in ext_nets_ids:
                ext_nets_ids.append(ext_net_id)
                self.allocate_floatingips(ext_net_id)
        existing_floatingips = self.get_floatingips()
        self.recreate_floatingips(src_floats, networks,
                                  existing_nets, existing_floatingips)
        self.delete_redundant_floatingips(src_floats, existing_floatingips)

    def allocate_floatingips(self, ext_net_id):
        try:
            while True:
                self.neutron_client.create_floatingip({
                    'floatingip':
                        {'floating_network_id': ext_net_id}})
        except IpAddressGenerationFailureClient:
            LOG.info("| Floating IPs "
                     "were allocated in network %s" % ext_net_id)

    def recreate_floatingips(self, src_floats, src_nets,
                             existing_nets,
                             existing_floatingips):

        """ We recreate floating ips with the same parameters as on src cloud,
        because we can't determine floating ip address
        during allocation process. """

        for src_float in src_floats:
            tname = src_float['tenant_name']
            tenant_id = \
                self.identity_client.get_tenant_id_by_name(tname)
            ext_net_hash = \
                self.get_res_hash_by_id(src_nets,
                                        src_float['floating_network_id'])
            ext_net = self.get_res_by_hash(existing_nets, ext_net_hash)
            for floating in existing_floatingips:
                if floating['floating_ip_address'] == \
                        src_float['floating_ip_address']:
                    if floating['floating_network_id'] == ext_net['id']:
                        if floating['tenant_id'] != tenant_id:
                            id = floating['id']
                            self.neutron_client.delete_floatingip(id)
                            self.neutron_client.create_floatingip({
                                'floatingip':
                                    {'floating_network_id': ext_net['id'],
                                     'tenant_id': tenant_id}})

    def delete_redundant_floatingips(self, src_floats, existing_floatingips):
        src_floatingips = \
            [src_float['floating_ip_address'] for src_float in src_floats]
        for floatingip in existing_floatingips:
            if floatingip['floating_ip_address'] not in src_floatingips:
                self.neutron_client.delete_floatingip(floatingip['id'])

    def get_res_by_hash(self, existing_resources, resource_hash):
        for resource in existing_resources:
            if resource['res_hash'] == resource_hash:
                return resource

    def get_res_hash_by_id(self, resources, resource_id):
        for resource in resources:
            if resource['id'] == resource_id:
                return resource['res_hash']

    def get_resource_hash(self, neutron_resource, *args):
        list_info = list()
        for arg in args:
            if type(neutron_resource[arg]) is not list:
                list_info.append(neutron_resource[arg])
            else:
                for argitem in arg:
                    if type(argitem) is str:
                        argitem = argitem.lower()
                    list_info.append(argitem)
        hash_list = \
            [info.lower() if type(info) is str else info for info in list_info]
        hash_list.sort()
        return hash(tuple(hash_list))
