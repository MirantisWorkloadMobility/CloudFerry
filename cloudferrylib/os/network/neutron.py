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


import copy
import pprint

import ipaddr
import netaddr

from neutronclient.common import exceptions as neutron_exc
from neutronclient.v2_0 import client as neutron_client

from cloudferrylib.base import exception
from cloudferrylib.base import network
from cloudferrylib.os.identity import keystone as ksresource
from cloudferrylib.utils import cache
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)
DEFAULT_SECGR = 'default'


@cache.Cached(getter='get_subnets_list', modifier='create_network')
@cache.Cached(getter='get_networks_list', modifier='create_network')
@cache.Cached(getter='get_ports_list', modifier='create_port')
class NeutronNetwork(network.Network):

    """
    The main class for working with OpenStack Neutron client
    """

    def __init__(self, config, cloud):
        super(NeutronNetwork, self).__init__(config)
        self.cloud = cloud
        self.identity_client = cloud.resources[utl.IDENTITY_RESOURCE]
        self.filter_tenant_id = None
        self.ext_net_map = \
            utl.read_yaml_file(self.config.migrate.ext_net_map) or {}
        self.mysql_connector = cloud.mysql_connector('neutron')

    @property
    def neutron_client(self):
        return self.proxy(self.get_client(), self.config)

    def get_client(self):

        return neutron_client.Client(
            username=self.config.cloud.user,
            password=self.config.cloud.password,
            tenant_name=self.config.cloud.tenant,
            auth_url=self.config.cloud.auth_url,
            cacert=self.config.cloud.cacert,
            insecure=self.config.cloud.insecure,
            region_name=self.config.cloud.region
        )

    def read_info(self, **kwargs):

        """Get info about neutron resources:
        :rtype: Dictionary with all necessary neutron info
        """

        if kwargs.get('tenant_id'):
            tenant_id = self.filter_tenant_id = kwargs['tenant_id'][0]
        else:
            tenant_id = ''

        nets = self.get_networks(tenant_id)
        subnets = self.get_subnets(tenant_id)
        detached_ports = self.get_detached_ports(tenant_id)
        LOG.debug('List of detached ports: %s',
                  repr([p['id'] for p in detached_ports]))

        if self.filter_tenant_id is not None:
            shared_nets = self.get_shared_networks_raw()
            for net in shared_nets:
                # do not include the same network twice
                if net['id'] in [n['id'] for n in nets]:
                    continue
                nets.append(self.convert_networks(net, self.cloud))
                LOG.debug("Got shared network ID %s", net['id'])
                # Append subnets from the shared networks
                for subnet in net['subnets']:
                    # do not include the same subnets twice
                    if subnet['id'] in [sn['id'] for sn in subnets]:
                        continue
                    subnets.append(self.convert_subnets(subnet, self.cloud))
                    LOG.debug("Got shared subnet ID %s", subnet['id'])

            full_nets_list = self.get_networks()
        else:
            full_nets_list = nets

        # Get full list off busy segmentation IDs
        used_seg_ids = get_segmentation_ids_from_net_list(full_nets_list)

        routers = self.get_routers()
        subnet_ids = {sn['id'] for sn in subnets}
        for router in routers:
            router['subnet_ids'] = [sn_id for sn_id in router['subnet_ids']
                                    if sn_id in subnet_ids]

        info = {'networks': nets,
                'subnets': subnets,
                'routers': routers,
                'detached_ports': detached_ports,
                'floating_ips': self.get_floatingips(tenant_id),
                'security_groups': self.get_sec_gr_and_rules(tenant_id),
                'quota': self.get_quota(tenant_id),
                'meta': {
                    'segmentation_ids': used_seg_ids
                }}
        if self.config.migrate.keep_lbaas:
            info['lbaas'] = dict()
            info['lb_pools'] = self.get_lb_pools(tenant_id)
            info['lb_monitors'] = self.get_lb_monitors(tenant_id)
            info['lb_members'] = self.get_lb_members(tenant_id)
            info['lb_vips'] = self.get_lb_vips(tenant_id)
        return info

    def show_quota(self, tenant_id=''):
        return self.neutron_client.show_quota(tenant_id)

    def list_quotas(self):
        return self.neutron_client.list_quotas()['quotas']

    def get_quota(self, tenant_id):
        # return structure {'name_tenant': {'subnet': 10, ...}, ...}
        tenants = {}
        if not tenant_id:
            tenants_obj = self.identity_client.get_tenants_list()
            tenants = {t.id: t.name for t in tenants_obj}
        else:
            tenants[tenant_id] = self.identity_client.\
                try_get_tenant_name_by_id(tenant_id)
        data = {
        }
        if self.config.network.get_all_quota:
            for t_id, t_val in tenants.iteritems():
                data[t_val] = self.neutron_client.show_quota(t_id)
        else:
            for t in self.neutron_client.list_quotas()['quotas']:
                if (not tenant_id) or (tenant_id == t['tenant_id']):
                    tenant_name = self.identity_client.\
                        try_get_tenant_name_by_id(t['tenant_id'])
                    data[tenant_name] = {k: v
                                         for k, v in t.iteritems()
                                         if k != 'tenant_id'}
        return data

    def upload_quota(self, quota):
        identity = self.identity_client
        for q_name, q_val in quota.iteritems():
            tenant_id = identity.get_tenant_id_by_name(q_name)
            self.neutron_client.update_quota(tenant_id, q_val)

    def create_quota(self, tenant_id, quota):
        return self.neutron_client.update_quota(tenant_id, quota)

    def required_tenants(self, filter_tenant_id=None):
        old_filter_tanant_id = self.filter_tenant_id
        self.filter_tenant_id = filter_tenant_id

        tenant_ids = set()
        for shared_net in self.get_shared_networks_raw():
            tenant_ids.add(shared_net['tenant_id'])
        for router in self.get_routers_raw():
            tenant_ids.add(router['tenant_id'])

        self.filter_tenant_id = old_filter_tanant_id

        return list(tenant_ids)

    def deploy(self, info):
        """
        Deploy network resources to DST

        Have non trivial behavior when enabled keep_floatingip and
        change_router_ips. Example:
        Initial state:
            src cloud with router external ip 123.0.0.5
                and FloatingIP 123.0.0.4
        Migrate resources:
            1. Move FloatingIP to dst. On dst we have FloatingIP 123.0.0.4
            2. Create FloatingIP on dst as stub for router IP.
                On dst we have two FloatingIP [123.0.0.4, 123.0.0.5].
                IP 123.0.0.5 exists only in OpenStack DB and not crush
                src network.
            3. Create router on dst. (here is the main idea) As you see above,
                ips 123.0.0.4 and 123.0.0.5 already allocated,
                then OpenStack must allocate another ip for router
                (e.g. 123.0.0.6).
            4. FloatingIP 123.0.0.5 is not needed anymore.
                We use it on 1.3. step for not allow OpenStack create
                router with this ip. It will be released if you enable
                clean_router_ips_stub in config
        After resource migration we have:
            src router external ip 123.0.0.5 and FloatingIP 123.0.0.4
            dst router external ip 123.0.0.6 and FloatingIP 123.0.0.4
        """
        deploy_info = info
        self.upload_quota(deploy_info['quota'])
        self.upload_networks(deploy_info['networks'],
                             deploy_info['meta']['segmentation_ids'],
                             deploy_info['detached_ports'])
        dst_router_ip_ids = None
        if self.config.migrate.keep_floatingip:
            self.upload_floatingips(deploy_info['networks'],
                                    deploy_info['floating_ips'])
            if self.config.migrate.change_router_ips:
                subnets_map = {subnet['id']: subnet
                               for subnet in deploy_info['subnets']}
                router_ips = self.extract_router_ips_as_floating_ips(
                    subnets_map, deploy_info['routers'])
                dst_router_ip_ids = self.upload_floatingips(
                    deploy_info['networks'], router_ips)
        self.upload_routers(deploy_info['networks'],
                            deploy_info['subnets'],
                            deploy_info['routers'])
        if self.config.migrate.clean_router_ips_stub and dst_router_ip_ids:
            for router_ip_stub in dst_router_ip_ids:
                self.neutron_client.delete_floatingip(router_ip_stub)
        self.upload_neutron_security_groups(deploy_info['security_groups'])
        self.upload_sec_group_rules(deploy_info['security_groups'])
        if self.config.migrate.keep_lbaas:
            self.upload_lb_pools(deploy_info['lb_pools'],
                                 deploy_info['subnets'])
            self.upload_lb_monitors(deploy_info['lb_monitors'])
            self.associate_lb_monitors(deploy_info['lb_pools'],
                                       deploy_info['lb_monitors'])
            self.upload_lb_members(deploy_info['lb_members'],
                                   deploy_info['lb_pools'])
            self.upload_lb_vips(deploy_info['lb_vips'],
                                deploy_info['lb_pools'],
                                deploy_info['subnets'])
        return deploy_info

    def extract_router_ips_as_floating_ips(self, subnets, routers_info):
        result = []
        tenant = self.config.migrate.router_ips_stub_tenant
        for router_info in routers_info:
            router = Router(router_info, subnets)
            tenant_name = tenant if tenant else router.tenant_name
            if router.ext_net_id:
                result.append({'tenant_name': tenant_name,
                               'floating_network_id': router.ext_net_id,
                               'floating_ip_address': router.ext_ip})
        return result

    def get_mac_by_ip(self, ip_address, instance_id):
        for port in self.get_ports_list(device_id=instance_id):
            for fixed_ip_info in port['fixed_ips']:
                if fixed_ip_info['ip_address'] == ip_address:
                    return port["mac_address"]

    def get_instance_network_info(self, instance_id):
        ports = []
        for port in self.get_ports_list(device_id=instance_id):
            ports.append({
                'ip_addresses': [x['ip_address'] for x in port['fixed_ips']],
                'mac_address': port['mac_address'],
                'floatingip': self.get_port_floating_ip(port['id']),
                'allowed_address_pairs': port.get('allowed_address_pairs', []),
            })
        return ports

    def get_port_floating_ip(self, port_id):
        floating_ips = self.neutron_client.list_floatingips(
            port_id=port_id)['floatingips']
        if floating_ips:
            LOG.debug('Got %d floating IP for port %s',
                      len(floating_ips), port_id)
            return floating_ips[0]['floating_ip_address']
        else:
            return None

    def get_ports_list(self, **kwargs):
        return self.neutron_client.list_ports(**kwargs)['ports']

    def create_port(self, net_id, mac_address, ip_addresses, tenant_id,
                    keep_ip, sg_ids=None, allowed_address_pairs=None):
        param_create_port = {'network_id': net_id,
                             'tenant_id': tenant_id}
        if mac_address:
            param_create_port['mac_address'] = mac_address
        if sg_ids:
            param_create_port['security_groups'] = sg_ids
        if keep_ip:
            param_create_port['fixed_ips'] = [{"ip_address": ip}
                                              for ip in ip_addresses]
        if allowed_address_pairs is not None:
            param_create_port['allowed_address_pairs'] = allowed_address_pairs
        with ksresource.AddAdminUserToNonAdminTenant(
                self.identity_client.keystone_client,
                self.config.cloud.user,
                self.config.cloud.tenant):
            LOG.debug("Creating port IP '%s', MAC '%s' on net '%s'",
                      param_create_port.get('fixed_ips'), mac_address, net_id)
            return self.neutron_client.create_port(
                {'port': param_create_port})['port']

    def delete_port(self, port_id):
        return self.neutron_client.delete_port(port_id)

    def get_network(self, network_info, tenant_id, keep_ip=False):
        if keep_ip:
            addresses = [ipaddr.IPAddress(ip)
                         for ip in network_info['ip_addresses']]
            private = self.neutron_client.list_networks(
                tenant_id=tenant_id)['networks']
            shared = self.neutron_client.list_networks(shared=True)['networks']
            for net in private + shared:
                subnets = self.neutron_client.list_subnets(
                    network_id=net['id'])['subnets']
                if all(any(ipaddr.IPNetwork(subnet['cidr']).Contains(ip)
                           for subnet in subnets)
                       for ip in addresses):
                    return net
        if 'id' in network_info:
            networks = self.neutron_client.list_networks(
                id=network_info['id'])['networks']
            if len(networks) > 0:
                return networks[0]
        if 'name' in network_info:
            networks = self.neutron_client.list_networks(
                name=network_info['name'])['networks']
            if len(networks) > 0:
                return networks[0]
        LOG.error('Failed to find network %s in tenant %s; keep_ip = %s',
                  repr(network_info), tenant_id, keep_ip)
        raise exception.AbortMigrationError("Can't find suitable network")

    def check_existing_port(self, network_id, mac=None, ip_address=None,
                            ip_addresses=None, existing_ports=None):
        if ip_addresses is None:
            ip_addresses = []
        if ip_address is not None and ip_address not in ip_addresses:
            ip_addresses.append(ip_address)
        if existing_ports is None:
            existing_ports = self.get_ports_list(
                fields=['network_id', 'mac_address', 'id', 'fixed_ips',
                        'device_owner'],
                network_id=network_id)
        for port in existing_ports:
            if port['network_id'] != network_id:
                continue
            if port['mac_address'] == mac:
                return port
            for fixed_ip in port['fixed_ips']:
                if fixed_ip['ip_address'] in ip_addresses:
                    return port
        return None

    @staticmethod
    def convert(neutron_object, cloud, obj_name):
        """Convert OpenStack Neutron network object to CloudFerry object.

        :param neutron_object: Direct OS NeutronNetwork object to convert,
        :cloud:                Cloud object,
        :obj_name:             Name of NeutronNetwork object to convert.
                               List of possible values:
                               'network', 'subnet', 'router', 'floating_ip',
                               'security_group', 'rule'.
        """

        obj_map = {
            'network': NeutronNetwork.convert_networks,
            'subnet': NeutronNetwork.convert_subnets,
            'router': NeutronNetwork.convert_routers,
            'floating_ip': NeutronNetwork.convert_floatingips,
            'security_group': NeutronNetwork.convert_security_groups,
            'rule': NeutronNetwork.convert_rules,
            'lb_pool': NeutronNetwork.convert_lb_pools,
            'lb_member': NeutronNetwork.convert_lb_members,
            'lb_monitor': NeutronNetwork.convert_lb_monitors,
            'lb_vip': NeutronNetwork.convert_lb_vips
        }

        return obj_map[obj_name](neutron_object, cloud)

    def convert_networks(self, net, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]
        get_tenant_name = identity_res.get_tenants_func()

        subnets = []
        subnets_hash = set()

        for subnet in net['subnets']:
            snet = self.convert_subnets(subnet, cloud)
            subnets.append(snet)
            subnets_hash.add(snet['res_hash'])

        result = {
            'name': net['name'],
            'id': net['id'],
            'admin_state_up': net['admin_state_up'],
            'shared': net['shared'],
            'tenant_id': net['tenant_id'],
            'tenant_name': get_tenant_name(net['tenant_id']),
            'subnets': subnets,
            'router:external': net['router:external'],
            'provider:physical_network': net['provider:physical_network'],
            'provider:network_type': net['provider:network_type'],
            'provider:segmentation_id': net['provider:segmentation_id'],
            'subnets_hash': subnets_hash,
            'meta': {},
        }

        res_hash = net_res.get_resource_hash(result,
                                             'name',
                                             'shared',
                                             'tenant_name',
                                             'router:external',
                                             'admin_state_up',
                                             'provider:physical_network',
                                             'provider:network_type')
        result['res_hash'] = res_hash
        return result

    @staticmethod
    def convert_subnets(snet, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        network_res = cloud.resources[utl.NETWORK_RESOURCE]
        get_tenant_name = identity_res.get_tenants_func()

        networks_list = network_res.get_networks_list()
        net = get_network_from_list_by_id(snet['network_id'], networks_list)

        cidr = str(netaddr.IPNetwork(snet['cidr']).cidr)

        result = {
            'name': snet['name'],
            'id': snet['id'],
            'enable_dhcp': snet['enable_dhcp'],
            'allocation_pools': snet['allocation_pools'],
            'gateway_ip': snet['gateway_ip'],
            'ip_version': snet['ip_version'],
            'cidr': cidr,
            'network_name': net['name'],
            'external': net['router:external'],
            'network_id': snet['network_id'],
            'tenant_name': get_tenant_name(snet['tenant_id']),
            'dns_nameservers': snet['dns_nameservers'],
            'meta': {},
        }

        res_hash = network_res.get_resource_hash(result,
                                                 'name',
                                                 'enable_dhcp',
                                                 'ip_version',
                                                 'gateway_ip',
                                                 'cidr',
                                                 'allocation_pools',
                                                 'tenant_name',
                                                 'network_name')

        result['res_hash'] = res_hash

        return result

    @staticmethod
    def convert_routers(router, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func()

        result = {
            'name': router['name'],
            'id': router['id'],
            'admin_state_up': router['admin_state_up'],
            'external_gateway_info': router['external_gateway_info'],
            'tenant_name': get_tenant_name(router['tenant_id']),
            'meta': {},
        }
        result.update(net_res.get_ports_info(router))

        if router['external_gateway_info']:
            networks_list = net_res.get_networks_list()
            ext_id = router['external_gateway_info']['network_id']
            ext_net = get_network_from_list_by_id(ext_id, networks_list)

            result['ext_net_name'] = ext_net['name']
            result['ext_net_tenant_name'] = get_tenant_name(
                ext_net['tenant_id'])
            result['ext_net_id'] = router['external_gateway_info'][
                'network_id']

        res_hash = net_res.get_resource_hash(result,
                                             'name',
                                             'tenant_name')

        result['res_hash'] = res_hash

        return result

    @staticmethod
    def convert_floatingips(floating, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func()

        networks_list = net_res.get_networks_list()
        ext_id = floating['floating_network_id']
        extnet = get_network_from_list_by_id(ext_id, networks_list)

        result = {
            'id': floating['id'],
            'tenant_id': floating['tenant_id'],
            'floating_network_id': ext_id,
            'network_name': extnet['name'],
            'ext_net_tenant_name': get_tenant_name(extnet['tenant_id']),
            'tenant_name': get_tenant_name(floating['tenant_id']),
            'fixed_ip_address': floating['fixed_ip_address'],
            'floating_ip_address': floating['floating_ip_address'],
            'port_id': floating['port_id'],
            'meta': {},
        }

        return result

    @staticmethod
    def convert_rules(rule, cloud):
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        rule_hash = net_res.get_resource_hash(rule,
                                              'direction',
                                              'remote_ip_prefix',
                                              'protocol',
                                              'port_range_min',
                                              'port_range_max',
                                              'ethertype')

        result = {
            'remote_group_id': rule['remote_group_id'],
            'direction': rule['direction'],
            'remote_ip_prefix': rule['remote_ip_prefix'],
            'protocol': rule['protocol'],
            'port_range_min': rule['port_range_min'],
            'port_range_max': rule['port_range_max'],
            'ethertype': rule['ethertype'],
            'security_group_id': rule['security_group_id'],
            'rule_hash': rule_hash,
            'meta': dict()
        }

        return result

    @staticmethod
    def convert_security_groups(sec_gr, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func(
            return_default_tenant=False)

        result = {
            'name': sec_gr['name'],
            'id': sec_gr['id'],
            'tenant_id': sec_gr['tenant_id'],
            'tenant_name': get_tenant_name(sec_gr['tenant_id']),
            'description': sec_gr['description'],
            'security_group_rules': [NeutronNetwork.convert(gr, cloud, 'rule')
                                     for gr in sec_gr['security_group_rules']],
            'meta': {},
        }

        res_hash = net_res.get_resource_hash(result,
                                             'name',
                                             'tenant_name',
                                             'description')

        result['res_hash'] = res_hash

        return result

    @staticmethod
    def convert_lb_pools(pool, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func(
            return_default_tenant=False)

        result = {
            'name': pool['name'],
            'id': pool['id'],
            'description': pool['description'],
            'lb_method': pool['lb_method'],
            'protocol': pool['protocol'],
            'subnet_id': pool['subnet_id'],
            'provider': pool.get('provider'),
            'tenant_id': pool['tenant_id'],
            'tenant_name': get_tenant_name(pool['tenant_id']),
            'health_monitors': pool['health_monitors'],
            'members': pool['members'],
            'meta': {}
        }

        res_hash = net_res.get_resource_hash(result,
                                             'name',
                                             'tenant_name',
                                             'lb_method',
                                             'protocol')
        result['res_hash'] = res_hash

        return result

    @staticmethod
    def convert_lb_monitors(monitor, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func(
            return_default_tenant=False)

        result = {
            'id': monitor['id'],
            'tenant_id': monitor['tenant_id'],
            'tenant_name': get_tenant_name(monitor['tenant_id']),
            'type': monitor['type'],
            'delay': monitor['delay'],
            'timeout': monitor['timeout'],
            'max_retries': monitor['max_retries'],
            'url_path': monitor.get('url_path', None),
            'expected_codes': monitor.get('expected_codes', None),
            'pools': monitor.get('pools'),
            'meta': {}
        }

        res_hash = net_res.get_resource_hash(result,
                                             'tenant_name',
                                             'type',
                                             'delay',
                                             'timeout',
                                             'max_retries')

        result['res_hash'] = res_hash

        return result

    @staticmethod
    def convert_lb_members(member, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func(
            return_default_tenant=False)

        result = {
            'id': member['id'],
            'pool_id': member['pool_id'],
            'address': member['address'],
            'protocol_port': member['protocol_port'],
            'weight': member['weight'],
            'tenant_id': member['tenant_id'],
            'tenant_name': get_tenant_name(member['tenant_id']),
            'meta': {}
        }

        res_hash = net_res.get_resource_hash(result,
                                             'address',
                                             'protocol_port',
                                             'weight',
                                             'tenant_name')

        result['res_hash'] = res_hash

        return result

    @staticmethod
    def convert_lb_vips(vip, cloud):
        identity_res = cloud.resources[utl.IDENTITY_RESOURCE]
        net_res = cloud.resources[utl.NETWORK_RESOURCE]

        get_tenant_name = identity_res.get_tenants_func(
            return_default_tenant=False)

        result = {
            'name': vip['name'],
            'id': vip['id'],
            'description': vip['description'],
            'address': vip['address'],
            'protocol': vip['protocol'],
            'protocol_port': vip['protocol_port'],
            'pool_id': vip['pool_id'],
            'connection_limit': vip['connection_limit'],
            'session_persistence': vip.get('session_persistence', None),
            'tenant_id': vip['tenant_id'],
            'subnet_id': vip['subnet_id'],
            'tenant_name': get_tenant_name(vip['tenant_id']),
            'meta': {}
        }

        res_hash = net_res.get_resource_hash(result,
                                             'name',
                                             'address',
                                             'protocol',
                                             'protocol_port',
                                             'tenant_name')

        result['res_hash'] = res_hash

        return result

    def get_shared_networks_raw(self):
        """Returns list of external and shared networks in raw neutron object
        format"""
        external = self.get_networks_raw({'router:external': True})
        shared = self.get_networks_raw({'shared': True})

        return external + shared

    def get_networks_raw(self, search_dict):
        """Groups networks with subnets in raw `NeutronClient` format"""

        neutron = self.neutron_client
        nets = neutron.list_networks(**search_dict)['networks']
        subnets_list = self.get_subnets_list()

        for net in nets:
            subnets = []
            for subnet_id in net['subnets']:
                subnets.append(get_subnet_from_list_by_id(subnet_id,
                                                          subnets_list))
            net['subnets'] = subnets

        return nets

    def get_networks(self, tenant_id=''):
        LOG.info("Get networks...")
        networks = self.get_networks_raw({'tenant_id': tenant_id})
        networks_info = []

        for net in networks:
            cf_net = self.convert_networks(net, self.cloud)
            LOG.debug("Getting info about network '%s' (%s):\n%s",
                      cf_net['name'], cf_net['id'], pprint.pformat(cf_net))
            networks_info.append(cf_net)

        LOG.info("Done.")
        return networks_info

    def get_networks_list(self, tenant_id=''):
        return self.neutron_client.list_networks(
            tenant_id=tenant_id)['networks']

    def get_subnets_list(self, tenant_id=''):
        return self.neutron_client.list_subnets(tenant_id=tenant_id)['subnets']

    def get_detached_ports(self, tenant_id=''):
        ports = self.neutron_client.list_ports(tenant_id=tenant_id)['ports']
        return [p for p in ports if not p['device_owner']]

    def get_subnets(self, tenant_id=''):
        LOG.info("Get subnets...")
        subnets = self.get_subnets_list(tenant_id)
        subnets_info = []

        for snet in subnets:
            subnet = self.convert(snet, self.cloud, 'subnet')
            subnets_info.append(subnet)

        LOG.info("Done")
        return subnets_info

    def reset_subnet_dhcp(self, subnet_id, dhcp_flag):
        LOG.debug('Setting enable_dhcp to %s for subnet %s',
                  dhcp_flag, subnet_id)
        subnet_info = {
            'subnet':
            {
                'enable_dhcp': dhcp_flag
            }
        }
        return self.neutron_client.update_subnet(subnet_id, subnet_info)

    def get_ports_info(self, router):
        LOG.debug("Finding all ports connected to router '%s'", router['name'])
        ports_list = self.get_ports_list()
        ports = get_ports_by_device_id_from_list(router['id'], ports_list)
        subnet_ids = []
        ips = []

        for port in ports:
            for ip_info in port['fixed_ips']:
                ips.append(ip_info['ip_address'])
                subnet_ids.append(ip_info['subnet_id'])

        return {'ips': set(ips), 'subnet_ids': set(subnet_ids)}

    def get_routers_raw(self):
        routers = self.neutron_client.list_routers()['routers']
        if self.filter_tenant_id:
            subnet_ids = {
                sn['id']
                for sn in self.get_subnets_list(self.filter_tenant_id)}

            return [r for r in routers
                    if (r['tenant_id'] == self.filter_tenant_id or
                        subnet_ids & self.get_ports_info(r)['subnet_ids'])]

        return routers

    def get_routers(self):
        LOG.info("Get routers")

        return [self.convert_routers(r, self.cloud)
                for r in self.get_routers_raw()]

    def get_floatingips(self, tenant_id=''):
        LOG.info("Get floatingips...")
        floatings = self.neutron_client.list_floatingips(
            tenant_id=tenant_id)['floatingips']
        floatingips_info = []

        for floating in floatings:
            floatingip_info = self.convert(floating, self.cloud, 'floating_ip')
            floatingips_info.append(floatingip_info)

        LOG.info("Done")
        return floatingips_info

    def get_security_groups(self, tenant_id=''):
        return self.neutron_client.list_security_groups(
            tenant_id=tenant_id)['security_groups']

    def get_sec_gr_and_rules(self, tenant_id=''):
        LOG.info("Getting security groups and rules...")
        service_tenant_name = self.config.cloud.service_tenant
        service_tenant_id = \
            self.identity_client.get_tenant_id_by_name(service_tenant_name)
        sec_grs = self.get_security_groups(tenant_id)
        sec_groups_info = []

        for sec_gr in sec_grs:
            if sec_gr['tenant_id'] != service_tenant_id:
                sec_gr_info = self.convert(sec_gr, self.cloud,
                                           'security_group')
                if not sec_gr_info['tenant_name']:
                    # Skip security group from undefined tenant
                    LOG.warning("Security group '%s' (%s) from tenant %s "
                                "has been skipped.", sec_gr['name'],
                                sec_gr['id'], sec_gr['tenant_id'])
                    continue
                sec_groups_info.append(sec_gr_info)

        LOG.info("Done")
        return sec_groups_info

    def get_lb_pools(self, tenant_id=''):
        LOG.info("Getting load balancer pools...")
        pools = self.neutron_client.list_pools(tenant_id=tenant_id)['pools']
        pools_info = []

        for pool in pools:
            pool_info = self.convert(pool, self.cloud, 'lb_pool')
            pools_info.append(pool_info)

        LOG.info("Done")
        return pools_info

    def get_lb_monitors(self, tenant_id=''):
        LOG.info("Getting load balancer monitors...")
        monitors = \
            self.neutron_client.list_health_monitors(
                tenant_id=tenant_id)['health_monitors']
        monitors_info = []

        for mon in monitors:
            mon_info = self.convert(mon, self.cloud, 'lb_monitor')
            monitors_info.append(mon_info)

        LOG.info("Done")
        return monitors_info

    def get_lb_members(self, tenant_id=''):
        LOG.info("Getting load balancer members...")
        members = self.neutron_client.list_members(
            tenant_id=tenant_id)['members']
        members_info = []

        for member in members:
            member_info = self.convert(member, self.cloud, 'lb_member')
            members_info.append(member_info)

        LOG.info("Done")
        return members_info

    def get_lb_vips(self, tenant_id=''):
        LOG.info("Getting load balancer VIPs...")
        vips = self.neutron_client.list_vips(
            tenant_id=tenant_id)['vips']
        vips_info = []

        for vip in vips:
            vip_info = self.convert(vip, self.cloud, 'lb_vip')
            vips_info.append(vip_info)

        LOG.info("Done")
        return vips_info

    def upload_lb_vips(self, vips, pools, subnets):
        LOG.info("Creating load balancer VIPs on destination")
        existing_vips = self.get_lb_vips()
        existing_vips_hashlist = [ex_vip['res_hash']
                                  for ex_vip in existing_vips]
        existing_pools = self.get_lb_pools()
        existing_snets = self.get_subnets()
        for vip in vips:
            if not vip['tenant_name']:
                continue
            if vip['res_hash'] not in existing_vips_hashlist:
                tenant_id = self.identity_client.get_tenant_id_by_name(
                    vip['tenant_name'])
                pool_hash = self.get_res_hash_by_id(pools, vip['pool_id'])
                dst_pool = self.get_res_by_hash(existing_pools, pool_hash)
                snet_hash = self.get_res_hash_by_id(subnets, vip['subnet_id'])
                dst_subnet = self.get_res_by_hash(existing_snets, snet_hash)
                vip_info = {
                    'vip': {
                        'name': vip['name'],
                        'description': vip['description'],
                        'address': vip['address'],
                        'protocol': vip['protocol'],
                        'protocol_port': vip['protocol_port'],
                        'connection_limit': vip['connection_limit'],
                        'pool_id': dst_pool['id'],
                        'tenant_id': tenant_id,
                        'subnet_id': dst_subnet['id']
                    }
                }
                if vip['session_persistence']:
                    vip_info['vip']['session_persistence'] = \
                        vip['session_persistence']
                vip['meta']['id'] = self.neutron_client.create_vip(
                    vip_info)['vip']['id']
            else:
                LOG.info("| Dst cloud already has the same VIP "
                         "with address %s in tenant %s",
                         vip['address'], vip['tenant_name'])
        LOG.info("Done")

    def upload_lb_members(self, members, pools):
        LOG.info("Creating load balancer members...")
        existing_members = self.get_lb_members()
        existing_members_hashlist = \
            [ex_member['res_hash'] for ex_member in existing_members]
        existing_pools = self.get_lb_pools()
        for member in members:
            if not member['tenant_name']:
                continue
            if member['res_hash'] not in existing_members_hashlist:
                tenant_id = self.identity_client.get_tenant_id_by_name(
                    member['tenant_name'])
                pool_hash = self.get_res_hash_by_id(pools, member['pool_id'])
                dst_pool = self.get_res_by_hash(existing_pools, pool_hash)
                member_info = {
                    'member': {
                        'protocol_port': member["protocol_port"],
                        'address': member['address'],
                        'pool_id': dst_pool['id'],
                        'tenant_id': tenant_id
                    }
                }
                member['meta']['id'] = self.neutron_client.create_member(
                    member_info)['member']['id']
            else:
                LOG.info("| Dst cloud already has the same member "
                         "with address %s in tenant %s",
                         member['address'], member['tenant_name'])
        LOG.info("Done")

    def upload_lb_monitors(self, monitors):
        LOG.info("Creating load balancer monitors on destination...")
        existing_mons = self.get_lb_monitors()
        existing_mons_hashlist = \
            [ex_mon['res_hash'] for ex_mon in existing_mons]
        for mon in monitors:
            if not mon['tenant_name']:
                continue
            if mon['res_hash'] not in existing_mons_hashlist:
                tenant_id = self.identity_client.get_tenant_id_by_name(
                    mon['tenant_name'])
                mon_info = {
                    'health_monitor':
                        {
                            'tenant_id': tenant_id,
                            'type': mon['type'],
                            'delay': mon['delay'],
                            'timeout': mon['timeout'],
                            'max_retries': mon['max_retries']
                        }
                }
                if mon['url_path']:
                    mon_info['health_monitor']['url_path'] = mon['url_path']
                    mon_info['health_monitor']['expected_codes'] = \
                        mon['expected_codes']
                mon['meta']['id'] = self.neutron_client.create_health_monitor(
                    mon_info)['health_monitor']['id']
            else:
                LOG.info("| Dst cloud already has the same healthmonitor "
                         "with type %s in tenant %s",
                         mon['type'], mon['tenant_name'])
        LOG.info("Done")

    def associate_lb_monitors(self, pools, monitors):
        LOG.info("Associating balancer monitors on destination...")
        existing_pools = self.get_lb_pools()
        existing_monitors = self.get_lb_monitors()
        for pool in pools:
            if not pool['tenant_name']:
                continue
            pool_hash = self.get_res_hash_by_id(pools, pool['id'])
            dst_pool = self.get_res_by_hash(existing_pools, pool_hash)
            for monitor_id in pool['health_monitors']:
                monitor_hash = self.get_res_hash_by_id(monitors, monitor_id)
                dst_monitor = self.get_res_by_hash(existing_monitors,
                                                   monitor_hash)
                if dst_monitor['id'] not in dst_pool['health_monitors']:
                    dst_monitor_info = {
                        'health_monitor': {
                            'id': dst_monitor['id']
                        }
                    }
                    self.neutron_client.associate_health_monitor(
                        dst_pool['id'], dst_monitor_info)
                else:
                    LOG.info(
                        "Dst pool with name %s already has associated the "
                        "healthmonitor with id %s in tenant %s",
                        dst_pool['name'], dst_monitor['id'],
                        dst_monitor['tenant_name'])
        LOG.info("Done")

    def upload_lb_pools(self, pools, subnets):
        LOG.info("Creating load balancer pools on destination...")
        existing_pools = self.get_lb_pools()
        existing_pools_hashlist = \
            [ex_pool['res_hash'] for ex_pool in existing_pools]
        existing_subnets = self.get_subnets()
        for pool in pools:
            if pool['res_hash'] not in existing_pools_hashlist and \
                    pool['tenant_name']:
                tenant_id = self.identity_client.get_tenant_id_by_name(
                    pool['tenant_name'])
                snet_hash = self.get_res_hash_by_id(subnets, pool['subnet_id'])
                snet_id = self.get_res_by_hash(existing_subnets,
                                               snet_hash)['id']
                pool_info = {
                    'pool': {
                        'name': pool['name'],
                        'description': pool['description'],
                        'tenant_id': tenant_id,
                        'subnet_id': snet_id,
                        'protocol': pool['protocol'],
                        'lb_method': pool['lb_method']
                    }
                }
                if pool.get('provider'):
                    pool_info['pool']['provider'] = pool.get('provider')
                LOG.debug("Creating LB pool '%s'", pool['name'])
                pool['meta']['id'] = \
                    self.neutron_client.create_pool(pool_info)['pool']['id']
            else:
                LOG.info("| Dst cloud already has the same pool "
                         "with name %s in tenant %s",
                         pool['name'], pool['tenant_name'])
        LOG.info("Done")

    def upload_neutron_security_groups(self, sec_groups):
        LOG.info("Creating neutron security groups on destination...")
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
        LOG.info("Done")

    def upload_sec_group_rules(self, sec_groups):
        LOG.info("Creating neutron security group rules on destination...")
        ex_secgrs = self.get_sec_gr_and_rules()
        for sec_gr in sec_groups:
            ex_secgr = \
                self.get_res_by_hash(ex_secgrs, sec_gr['res_hash'])
            if ex_secgr:
                exrules_hlist = \
                    [r['rule_hash'] for r in ex_secgr['security_group_rules']]
            else:
                exrules_hlist = []
            for rule in sec_gr['security_group_rules']:
                if rule['protocol'] \
                        and (rule['rule_hash'] not in exrules_hlist):
                    rinfo = \
                        {'security_group_rule': {
                            'direction': rule['direction'],
                            'protocol': rule['protocol'],
                            'port_range_min': rule['port_range_min'],
                            'port_range_max': rule['port_range_max'],
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
                    LOG.debug("Creating security group %s", rinfo)
                    new_rule = \
                        self.neutron_client.create_security_group_rule(rinfo)
                    rule['meta']['id'] = new_rule['security_group_rule']['id']
        LOG.info("Done")

    def upload_networks(self, networks, src_seg_ids, detached_ports):
        LOG.info("Creating networks on destination")
        identity = self.identity_client

        existing_networks = self.get_networks()

        # we need to handle duplicates in segmentation ids
        dst_seg_ids = get_segmentation_ids_from_net_list(existing_networks)

        for src_net in networks:
            network_detached_ports = [p for p in detached_ports
                                      if p['network_id'] == src_net['id']]

            # Check network for existence on destination cloud
            dst_net = self.get_dst_net_by_src_net(existing_networks, src_net)
            if dst_net:
                LOG.info("DST cloud already has the same "
                         "network with name '%s' in tenant '%s'",
                         src_net['name'], src_net['tenant_name'])
                self.deploy_detached_ports(dst_net, network_detached_ports)
                continue

            LOG.debug("Trying to create network '%s'", src_net['name'])
            tenant_id = identity.get_tenant_id_by_name(src_net['tenant_name'])

            if tenant_id is None:
                LOG.warning("Tenant '%s' is not available on destination! "
                            "Make sure you migrated identity (keystone) "
                            "resources! Skipping network '%s'.",
                            src_net['tenant_name'], src_net['name'])
                continue

            no_extnet_migration = (
                src_net.get('router:external') and
                not self.config.migrate.migrate_extnets or
                (src_net['id'] in self.ext_net_map))
            if no_extnet_migration:
                LOG.debug("External networks migration is disabled in the "
                          "config OR external networks mapping is enabled. "
                          "Skipping external network: '%s (%s)'",
                          src_net['name'], src_net['id'])
                continue

            # create dict, representing basic info about network
            network_info = {
                'network': {
                    'tenant_id': tenant_id,
                    'admin_state_up': src_net["admin_state_up"],
                    'shared': src_net["shared"],
                    'name': src_net['name'],
                    'router:external': src_net['router:external']
                }
            }

            phys_net = src_net["provider:physical_network"]
            network_type = src_net['provider:network_type']
            seg_id = src_net["provider:segmentation_id"]

            if phys_net or (src_net['provider:network_type'] in
                            ['gre', 'vxlan']):
                # Update network info with additional arguments.
                # We need to check if we have parameter
                # "provider:physical_network" or param
                # "provider:network_type" either is 'gre' or 'vxlan'.
                # If condition is satisfied, we need to specify 2 more params:
                # "provider:network_type" and "provider:segmentation_id".
                list_update_atr = ["provider:network_type"]
                if phys_net:
                    list_update_atr.append("provider:physical_network")
                for atr in list_update_atr:
                    network_info['network'].update({atr: src_net.get(atr)})

                # Check segmentation ID for overlapping
                # If it doesn't overlap with DST, save the same segmentation ID
                # Otherwise pick free segmentation ID, which does not overlap
                # with ANY segmentation ID on SRC
                if seg_id is not None:
                    # Segmentation ID exists; Check for overlapping
                    seg_id_overlaps = (network_type in dst_seg_ids and
                                       seg_id in dst_seg_ids[network_type])

                    if seg_id_overlaps:
                        # Choose the lowest free segmentation ID, that also
                        # does not overlap with SRC
                        new_seg_id = generate_new_segmentation_id(src_seg_ids,
                                                                  dst_seg_ids,
                                                                  network_type)

                        LOG.debug("'%s' segmentation ID '%s' overlaps with "
                                  "DST. Generating new one: '%s'.",
                                  network_type, seg_id, new_seg_id)

                        # Use it for network
                        network_info['network']['provider:segmentation_id'] = (
                            new_seg_id)

                        # Update DST segmentation IDs with the just created one
                        dst_seg_ids[network_type].append(new_seg_id)

                    else:
                        # Otherwise use original segmentation ID from SRC
                        network_info['network']['provider:segmentation_id'] = (
                            seg_id)

            created_network = self.create_network(src_net, network_info)
            self.deploy_detached_ports(created_network, network_detached_ports)

    def deploy_detached_ports(self, net, ports):
        for subnet in net['subnets']:
            self.reset_subnet_dhcp(subnet['id'], False)
        existing_ports = {p['id']: p
                          for p in self.get_ports_list(network_id=net['id'])}
        for port in ports:
            ip_addresses = [fip['ip_address'] for fip in port['fixed_ips']]
            existing_port = self.check_existing_port(
                net['id'], port['mac_address'],
                ip_addresses=ip_addresses,
                existing_ports=existing_ports.values())
            if existing_port is not None:
                if existing_port['mac_address'] == port['mac_address']:
                    LOG.debug('Port %s already migrated to %s',
                              port['id'], existing_port['id'])
                    continue

                if existing_port['device_owner'].startswith('network:') or \
                        not existing_port['device_owner']:
                    LOG.debug('Deleting port %s from DST', repr(existing_port))
                    self.delete_port(existing_port['id'])
                    del existing_ports[existing_port['id']]
                else:
                    raise exception.AbortMigrationError(
                        'Can\'t migrate port %s conflict with port %s' %
                        (port['id'], existing_port['id']))

            self.create_port(net['id'], port['mac_address'], ip_addresses,
                             net['tenant_id'], True)
        for subnet in net['subnets']:
            if subnet['enable_dhcp']:
                self.reset_subnet_dhcp(subnet['id'], True)

    def create_network(self, src_net, network_info):
        try:
            LOG.debug("creating network with args: '%s'",
                      pprint.pformat(network_info))
            created_net = self.neutron_client.create_network(network_info)
            created_net = created_net['network']
            LOG.info("Created net '%s'", created_net['name'])
        except neutron_exc.NeutronClientException as e:
            LOG.warning("Cannot create network on destination: %s. "
                        "Destination cloud already has the same network. May "
                        "result in port allocation errors, such as VM IP "
                        "allocation, floating IP allocation, router IP "
                        "allocation, etc.", e)
            return

        for snet in src_net['subnets']:
            subnet_info = {
                'subnet': {
                    'name': snet['name'],
                    'enable_dhcp': snet['enable_dhcp'],
                    'network_id': created_net['id'],
                    'cidr': snet['cidr'],
                    'allocation_pools': snet['allocation_pools'],
                    'gateway_ip': snet['gateway_ip'],
                    'ip_version': snet['ip_version'],
                    'dns_nameservers': snet['dns_nameservers'],
                    'tenant_id': created_net['tenant_id']
                }
            }
            try:
                created_subnet = self.neutron_client.create_subnet(subnet_info)
                created_subnet = created_subnet['subnet']
                snet['meta']['id'] = created_subnet['id']

                LOG.info("Created subnet '%s' in net '%s'",
                         created_subnet['cidr'], created_net['name'])
                created_net['subnets'].append(created_subnet)
            except neutron_exc.NeutronClientException:
                LOG.info("Subnet '%s' (%s) already exists, skipping",
                         snet['name'], snet['cidr'])

        return created_net

    def upload_routers(self, networks, subnets, routers):
        LOG.info("Creating routers on destination")
        existing_subnets = self.get_subnets()
        existing_routers = self.get_routers()
        for router in routers:
            tenant_id = self.identity_client.get_tenant_id_by_name(
                router['tenant_name'])
            r_info = {'router': {'name': router['name'],
                                 'tenant_id': tenant_id}}
            existing_router = self.get_res_by_hash(existing_routers,
                                                   router['res_hash'])
            if not existing_router:
                LOG.debug("Creating router %s", pprint.pformat(r_info))
                existing_router = self.convert_routers(
                    self.neutron_client.create_router(r_info)['router'],
                    self.cloud)
            router['meta']['id'] = existing_router['id']
            self.add_router_interfaces(router, existing_router, subnets,
                                       existing_subnets)

            ex_gw_info = router['external_gateway_info']
            if ex_gw_info:
                self.add_router_gateway(existing_router, router['ext_net_id'],
                                        networks,
                                        ex_gw_info.get('enable_snat'))

    def add_router_gateway(self, dst_router, ext_net_id, src_nets,
                           set_snat=None):
        """
        :param set_snat: possible values:
         1. `None` - do not update, useful in cases when destination cloud does
            not support SNAT for external networks (pre-icehouse);
         2. `True` - enable SNAT
         3. `False` - disable SNAT
        """

        dst_nets = self.get_networks()
        dst_net_id = self.get_new_extnet_id(ext_net_id, src_nets, dst_nets)
        if dst_net_id:
            info = {'network_id': dst_net_id}
            if set_snat is not None:
                info['enable_snat'] = set_snat
            LOG.debug("Setting the external network (%s) gateway for a router "
                      "'%s' (%s)", dst_net_id, dst_router['name'],
                      dst_router['id'])
            self.neutron_client.add_gateway_router(dst_router['id'], info)
        else:
            LOG.warning('External (%s) network is not exists on destination',
                        ext_net_id)

    def add_router_interfaces(self, src_router, dst_router, src_subnets,
                              dst_subnets):
        for subnet_id in src_router['subnet_ids']:
            subnet_hash = self.get_res_hash_by_id(src_subnets, subnet_id)

            src_subnet = self.get_res_by_hash(src_subnets, subnet_hash)
            if src_subnet['external']:
                LOG.debug("NOT connecting subnet '%s' to router '%s' because "
                          "it's connected to external network", subnet_id,
                          dst_router['name'])
                continue

            existing_subnet = self.get_res_by_hash(dst_subnets, subnet_hash)
            if existing_subnet['id'] in dst_router['subnet_ids']:
                continue

            LOG.debug("Adding subnet '%s' to router '%s'", subnet_id,
                      dst_router['name'])
            try:
                self.neutron_client.add_interface_router(
                    dst_router['id'],
                    {"subnet_id": existing_subnet['id']})
            except neutron_exc.NeutronClientException as e:
                LOG.debug(e, exc_info=True)
                LOG.warning("Couldn't add interface to subnet %s to router %s:"
                            "\n%s", existing_subnet['id'], dst_router['id'], e)

    def upload_floatingips(self, networks, src_floats):
        """Creates floating IPs on destination

        Process:
         1. Create floating IP on destination using neutron APIs in particular
            tenant. This allocates first IP address available in external
            network.
         2. If keep_floating_ips option is set:
         2.1. Modify IP address of a floating IP to be the same as on
              destination. This is done from the DB level.
         2.2. Else - do not modify floating IP address
         3. Return list of ID of new floating IPs
        """
        LOG.info("Uploading floating IPs...")
        existing_networks = self.get_networks()
        new_floating_ids = []
        fips_dst = self.neutron_client.list_floatingips()['floatingips']
        ipfloatings = {fip['floating_ip_address']: fip['id']
                       for fip in fips_dst}
        for fip in src_floats:
            ip = fip['floating_ip_address']
            if ip in ipfloatings:
                new_floating_ids.append(ipfloatings[ip])
                continue
            with ksresource.AddAdminUserToNonAdminTenant(
                    self.identity_client.keystone_client,
                    self.config.cloud.user,
                    fip['tenant_name']):

                ext_net_id = self.get_new_extnet_id(
                    fip['floating_network_id'], networks, existing_networks)

                if ext_net_id is None:
                    LOG.info("No external net for floating IP, make sure all "
                             "external networks migrated. Skipping floating "
                             "IP '%s'", fip['floating_ip_address'])
                    continue

                tenant = self.identity_client.keystone_client.tenants.find(
                    name=fip['tenant_name'])

                new_fip = {
                    'floatingip': {
                        'floating_network_id': ext_net_id,
                        'tenant_id': tenant.id
                    }
                }
                created_fip = self.create_floatingip(new_fip)
                if created_fip is None:
                    continue

            fip_id = created_fip['id']
            new_floating_ids.append(fip_id)
            sqls = [('UPDATE IGNORE floatingips '
                     'SET floating_ip_address = "{ip}" '
                     'WHERE id = "{fip_id}"').format(ip=ip, fip_id=fip_id),
                    ('UPDATE IGNORE ipallocations '
                     'SET ip_address = "{ip}" '
                     'WHERE port_id = ('
                         'SELECT floating_port_id '
                         'FROM floatingips '
                         'WHERE id = "{fip_id}")').format(
                        ip=ip, fip_id=fip_id),
                    ('DELETE FROM ipavailabilityranges '
                     'WHERE allocation_pool_id in ( '
                         'SELECT id '
                         'FROM ipallocationpools '
                         'WHERE subnet_id = ( '
                             'SELECT subnet_id '
                             'FROM ipallocations '
                             'WHERE port_id = ( '
                             'SELECT floating_port_id '
                             'FROM floatingips '
                             'WHERE id = "{fip_id}")))').format(
                        fip_id=fip_id)]
            LOG.debug(sqls)
            dst_mysql = self.mysql_connector
            dst_mysql.batch_execute(sqls)

        LOG.info("Done")
        return new_floating_ids

    def create_floatingip(self, fip):
        try:
            LOG.debug("Creating FIP on net '%s'",
                      fip['floatingip']['floating_network_id'])
            created = self.neutron_client.create_floatingip(fip)
            return created['floatingip']
        except neutron_exc.NeutronClientException as e:
            LOG.warning("Unable to create floating IP on destination: '%s'", e)

    def update_floatingip(self, floatingip_id, port_id=None):
        update_dict = {'floatingip': {'port_id': port_id}}
        LOG.debug("Associating floating IP '%s' with port '%s'",
                  floatingip_id, port_id)
        return self.neutron_client.update_floatingip(floatingip_id,
                                                     update_dict)

    @staticmethod
    def get_res_by_hash(existing_resources, resource_hash):
        for resource in existing_resources:
            if resource['res_hash'] == resource_hash:
                return resource

    @staticmethod
    def get_res_hash_by_id(resources, resource_id):
        for resource in resources:
            if resource['id'] == resource_id:
                return resource['res_hash']

    @staticmethod
    def get_resource_hash(neutron_resource, *args):
        net_res = copy.deepcopy(neutron_resource)
        list_info = list()
        for arg in args:
            if not isinstance(net_res[arg], list):
                list_info.append(net_res[arg])
            else:
                if arg == 'allocation_pools':
                    pools = net_res[arg]
                    net_res[arg] = [ip for pl in pools for ip in pl.values()]
                for argitem in net_res[arg]:
                    if isinstance(argitem, basestring):
                        argitem = argitem.lower()
                    list_info.append(argitem)
        hash_list = \
            [info.lower() if isinstance(info, basestring) else info
             for info in list_info]
        hash_list.sort()
        return hash(tuple(hash_list))

    def get_new_extnet_id(self, src_net_id, src_nets, dst_nets):
        """
        Get ID of similar external network form DST.

        :param src_net_id: External network ID from SRC cloud,
        :param src_nets: Networks list from SRC cloud,
        :param dst_nets: Networks list from DST cloud,

        :return unicode: External network ID from DST, that matches with the
                         similar network from SRC.
        """

        if src_net_id in self.ext_net_map:
            dst_net_id = self.ext_net_map[src_net_id]
        else:
            src_net = get_network_from_list_by_id(src_net_id, src_nets)
            dst_net = self.get_dst_net_by_src_net(dst_nets, src_net)

            if not dst_net:
                return

            dst_net_id = dst_net['id']

        return dst_net_id

    @staticmethod
    def get_dst_net_by_src_net(existing_networks, src_net):
        """
        Get the same Network object from DST cloud.

        :param existing_networks: Existing networks list on DST cloud,
        :param src_net: Network object from SRC,

        :return dict: Network object from DST, that matches with the same
                      network from SRC.
        """

        for net in existing_networks:
            if (net['res_hash'] == src_net['res_hash'] and
                    net['subnets_hash'] == src_net['subnets_hash']):
                return net


class Router(object):
    """
    Represents router_info, extract external ip.
    Router_info contain list of ips only in different order. Impossible to
    define external router ip.
    """
    def __init__(self, router_info, subnets):
        self.id = router_info['id']
        self.ext_net_id = router_info.get('ext_net_id', None)
        self.int_cidr = []
        self.tenant_name = router_info['tenant_name']
        if self.ext_net_id:
            subnet_ids = router_info['subnet_ids']
            for subnet_id in subnet_ids:
                subnet = subnets[subnet_id]
                if subnet['network_id'] == self.ext_net_id:
                    self.ext_cidr = subnet['cidr']
                    self.ext_subnet_id = subnet_id
                else:
                    self.int_cidr.append(subnet['cidr'])
            ext_network = ipaddr.IPNetwork(self.ext_cidr)
            for ip in router_info['ips']:
                if ext_network.Contains(ipaddr.IPAddress(ip)):
                    self.ext_ip = ip
                    break


def get_network_from_list_by_id(network_id, networks_list):
    """Get Neutron network by id from provided networks list.

    :param network_id: Neutron network ID
    :param networks_list: List of Neutron networks, where target network should
                          be searched
    """

    for net in networks_list:
        if net['id'] == network_id:
            return net

    LOG.warning("Cannot obtain network with id='%s' from provided networks "
                "list", network_id)


def get_subnet_from_list_by_id(subnet_id, subnets_list):
    """Get Neutron subnet by id from provided subnets list.

    :param subnet_id: Neutron subnet ID
    :param subnets_list: List of Neutron subnets, where target subnet should
                         be searched
    """

    for subnet in subnets_list:
        if subnet['id'] == subnet_id:
            return subnet

    LOG.warning("Cannot obtain subnet with id='%s' from provided subnets "
                "list", subnet_id)


def get_ports_by_device_id_from_list(device_id, ports_list):
    """Get Neutron ports by device ID from provided ports list.

    :param device_id: Port device ID
    :param ports_list: List of Neutron ports, where target ports should be
                       searched

    :result: List of ports, which are belong to specified device ID
    """

    ports = []

    for port in ports_list:
        if port['device_id'] == device_id:
            ports.append(port)

    if not ports:
        LOG.debug("There are no ports with device_id='%s' in provided list",
                  device_id)

    return ports


def get_network_from_list(ip, tenant_id, networks_list, subnets_list):
    """Get Neutron network by parameters from provided list.

    :param ip: IP address of VM from this network
    :param tenant_id: Tenant Id of VM in this network
    :param networks_list: List of Neutron networks, where target network
                          should be searched
    :param subnets_list: List of Neutron subnets, where target network
                         should be searched
    """

    instance_ip = ipaddr.IPAddress(ip)

    for subnet in subnets_list:
        network_id = subnet['network_id']
        net = get_network_from_list_by_id(network_id, networks_list)
        if subnet['tenant_id'] == tenant_id or net['shared']:
            if ipaddr.IPNetwork(subnet['cidr']).Contains(instance_ip):
                return get_network_from_list_by_id(network_id,
                                                   networks_list)


def get_segmentation_ids_from_net_list(networks):
    """Get busy segmentation IDs from provided networks list.

    We need to handle duplicates in segmentation ids.
    Neutron has different validation rules for different network types.

    For 'gre' and 'vxlan' network types there is no strong requirement
    for 'physical_network' attribute, if we want to have
    'segmentation_id', because traffic is encapsulated in L3 packets.

    For 'vlan' network type there is a strong requirement for
    'physical_network' attribute, if we want to have 'segmentation_id'.

    :result: Dictionary with busy segmentation IDs.
             Hash is used with structure {"gre": [1, 2, ...],
                                          "vlan": [1, 2, ...]}
    """

    used_seg_ids = {}

    for net in networks:
        network_has_segmentation_id = (
            net["provider:physical_network"] or
            (net["provider:network_type"] in ['gre', 'vxlan']))

        if network_has_segmentation_id:
            if net["provider:network_type"] not in used_seg_ids:
                used_seg_ids[net['provider:network_type']] = []
            if net["provider:segmentation_id"] is not None:
                used_seg_ids[net["provider:network_type"]].append(
                    net["provider:segmentation_id"])

    return used_seg_ids


def generate_new_segmentation_id(src_seg_ids, dst_seg_ids, network_type):
    """Generate new segmentation ID based on provided info with busy ones.

    Search for the lowest free segmentation ID. IDs '0' and '1' are reserved
    in most of network types, so start searching from '2'.

    For 'vlan' network type ID '4095' is the last one in available range and
    besides also reserved. Raise AbortMigrationError if reach this ID.

    :param src_seg_ids: Dictionary with busy segmentation IDs on SRC
    :param dst_seg_ids: Dictionary with busy segmentation IDs on DST
    :param network_type: Network type ('vlan', 'vxlan' or 'gre')

    :result int: New generated free segmentation ID
    """

    src_seg_ids = set(src_seg_ids.get(network_type, []))
    dst_seg_ids = set(dst_seg_ids.get(network_type, []))
    busy_seg_ids = src_seg_ids | dst_seg_ids

    free_seg_id = None
    counter = 2

    while free_seg_id is None:
        if counter not in busy_seg_ids:
            free_seg_id = counter
        counter += 1

    if free_seg_id >= 4095 and network_type == 'vlan':
        raise exception.AbortMigrationError("Segmentation IDs limit for 'vlan'"
                                            " network type has been exceeded")

    return free_seg_id
