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
from neutronclient.common import exceptions as neutronclient_exceptions

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl

LOG = utl.get_log(__name__)


class PrepareNetworks(action.Action):
    """Creates ports on destination with IPs and MACs preserved

    Process:
     - For each port on source create port with the same IP and MAC on
       destination

    Requirements:
     - Networks and subnets must be deployed on destination
    """

    def run(self, info=None, **kwargs):

        info_compute = copy.deepcopy(info)

        network_resource = self.cloud.resources[utl.NETWORK_RESOURCE]
        identity_resource = self.cloud.resources[utl.IDENTITY_RESOURCE]

        keep_ip = self.cfg.migrate.keep_ip

        instances = info_compute[utl.INSTANCES_TYPE]

        # Get all tenants, participated in migration process
        tenants = set()
        for instance in instances.values():
            tenants.add(instance[utl.INSTANCE_BODY]['tenant_name'])

        # disable DHCP in all subnets
        subnets = network_resource.get_subnets()
        for snet in subnets:
            if snet['tenant_name'] in tenants:
                network_resource.reset_subnet_dhcp(snet['id'], False)

        for (id_inst, inst) in instances.iteritems():
            params = []
            networks_info = inst[utl.INSTANCE_BODY][utl.INTERFACES]
            security_groups = inst[utl.INSTANCE_BODY]['security_groups']
            tenant_name = inst[utl.INSTANCE_BODY]['tenant_name']
            tenant_id = identity_resource.get_tenant_id_by_name(tenant_name)
            for src_net in networks_info:
                dst_net = network_resource.get_network(src_net, tenant_id,
                                                       keep_ip)
                mac_address = src_net['mac_address']
                ip_addresses = src_net['ip_addresses']
                for ip_address in ip_addresses:
                    port_dict = network_resource.check_existing_port(
                        dst_net['id'], mac_address, ip_address)
                    if port_dict:
                        network_resource.delete_port(port_dict['id'])
                sg_ids = []
                for sg in network_resource.get_security_groups():
                    if sg['tenant_id'] == tenant_id:
                        if sg['name'] in security_groups:
                            sg_ids.append(sg['id'])

                port = network_resource.create_port(
                    dst_net['id'], mac_address, ip_addresses, tenant_id,
                    keep_ip, sg_ids, src_net['allowed_address_pairs'])
                fip = None
                src_fip = src_net['floatingip']
                if src_fip:
                    dst_flotingips = network_resource.get_floatingips()
                    dst_flotingips_map = {
                        fl_ip['floating_ip_address']: fl_ip['id']
                        for fl_ip in dst_flotingips
                    }
                    # floating IP may be filtered and not exist on dest
                    dst_floatingip_id = dst_flotingips_map.get(src_fip)
                    if dst_floatingip_id is None:
                        LOG.warning("Floating IP '%s' is not available on "
                                    "destination, make sure floating IPs "
                                    "migrated correctly", src_fip)
                    else:
                        fip = {'dst_floatingip_id': dst_floatingip_id,
                               'dst_port_id': port['id']}
                params.append({'net-id': dst_net['id'],
                               'port-id': port['id'],
                               'floatingip': fip})
            instances[id_inst][utl.INSTANCE_BODY]['nics'] = params
        info_compute[utl.INSTANCES_TYPE] = instances

        # Reset DHCP to the original settings
        for snet in subnets:
            if snet['tenant_name'] in tenants:
                network_resource.reset_subnet_dhcp(snet['id'],
                                                   snet['enable_dhcp'])

        return {
            'info': info_compute
        }


class CreatePortsForVRRP(action.Action):
    """
    Action lists all ports on destination and creates port for each IP listed
    in allowed_address_pairs (so that nobody else could take this IP).
    This task must be executed after PrepareNetworks

    Use case:
     1) Allocate IP address by creating Neutron port.
     2) Then for each VM port add this IP address to allowed_address_pairs
        list.
     3) Configure VRRP on VMs (using keepalived or some other solution).
     4) You decided to migrate it.
    """

    def run(self, info=None, **kwargs):
        info_compute = copy.deepcopy(info)

        network_resource = self.cloud.resources[utl.NETWORK_RESOURCE]
        identity_resource = self.cloud.resources[utl.IDENTITY_RESOURCE]

        instances = info_compute[utl.INSTANCES_TYPE]

        # Get all tenants, participated in migration process
        tenants = set()
        for instance in instances.values():
            tenants.add(instance[utl.INSTANCE_BODY]['tenant_name'])

        # disable DHCP in all subnets
        subnets = network_resource.get_subnets()
        for snet in subnets:
            if snet['tenant_name'] in tenants:
                network_resource.reset_subnet_dhcp(snet['id'], False)

        for (id_inst, inst) in instances.iteritems():
            networks_info = inst[utl.INSTANCE_BODY][utl.INTERFACES]
            tenant_name = inst[utl.INSTANCE_BODY]['tenant_name']
            tenant_id = identity_resource.get_tenant_id_by_name(tenant_name)
            keep_ip = self.cfg.migrate.keep_ip
            for src_net in networks_info:
                allowed_address_pairs = src_net['allowed_address_pairs']
                if not allowed_address_pairs:
                    continue
                dst_net = network_resource.get_network(src_net, tenant_id,
                                                       keep_ip)
                for address_pair in allowed_address_pairs:
                    port_dict = network_resource.check_existing_port(
                        dst_net['id'],
                        ip_address=address_pair.get('ip_address'))
                    if port_dict is not None:
                        if port_dict['device_owner'] == 'network:dhcp':
                            network_resource.delete_port(port_dict['id'])
                        else:
                            continue
                    network_resource.create_port(
                        dst_net['id'], None, [address_pair.get('ip_address')],
                        tenant_id, True)

        # Reset DHCP to the original settings
        for snet in subnets:
            if snet['tenant_name'] in tenants:
                network_resource.reset_subnet_dhcp(snet['id'],
                                                   snet['enable_dhcp'])

        return {}
