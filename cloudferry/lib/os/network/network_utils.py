# Copyright 2016 Mirantis Inc.
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

import contextlib
import copy

from neutronclient.common import exceptions as neutron_exc

from cloudferry.lib.utils import log
from cloudferry.lib.utils import proxy_client
from cloudferry.lib.utils import utils

LOG = log.getLogger(__name__)


def prepare_networks(info, keep_ip, network_resource, identity_resource):
    info_compute = copy.deepcopy(info)

    instances = info_compute[utils.INSTANCES_TYPE]

    tenants = get_tenants(instances)

    # disable DHCP in all subnets
    with temporarily_disable_dhcp(network_resource, tenants):
        for (id_inst, inst) in instances.iteritems():
            params = []
            networks_info = inst[utils.INSTANCE_BODY][utils.INTERFACES]
            tenant_name = inst[utils.INSTANCE_BODY]['tenant_name']
            tenant_id = identity_resource.get_tenant_id_by_name(tenant_name)
            for src_net in networks_info:
                dst_net = network_resource.get_network(src_net, tenant_id,
                                                       keep_ip)
                mac_address = src_net['mac_address']
                ip_addresses = src_net['ip_addresses']

                delete_existing_ports_on_dst(network_resource,
                                             dst_net, ip_addresses,
                                             mac_address)

                sg_ids = get_security_groups_ids_for_tenant(network_resource,
                                                            inst, tenant_id)

                port = network_resource.create_port(
                    dst_net['id'], mac_address, ip_addresses, tenant_id,
                    keep_ip, sg_ids, src_net['allowed_address_pairs'])

                floating_ip = check_floating_ip(network_resource,
                                                src_net, port)

                params.append({'net-id': dst_net['id'],
                               'port-id': port['id'],
                               'floatingip': floating_ip})
            instances[id_inst][utils.INSTANCE_BODY]['nics'] = params
        info_compute[utils.INSTANCES_TYPE] = instances

    return info_compute


def get_tenants(instances):
    # Get all tenants, participated in migration process
    tenants = set()
    for instance in instances.values():
        tenants.add(instance[utils.INSTANCE_BODY]['tenant_name'])

    return tenants


@contextlib.contextmanager
def temporarily_disable_dhcp(network_resource, tenants):
    subnets = network_resource.get_subnets()
    disabled_subnets = []
    try:
        for snet in subnets:
            if snet['enable_dhcp'] and snet['tenant_name'] in tenants:
                # disable DHCP in all subnets
                network_resource.reset_subnet_dhcp(snet['id'], False)
                disabled_subnets.append(snet['id'])
        yield
    finally:
        for subnet_id in reversed(disabled_subnets):
            network_resource.reset_subnet_dhcp(subnet_id, True)


def delete_existing_ports_on_dst(network_resource,
                                 dst_net,
                                 ip_addresses,
                                 mac_address):

    for ip_address in ip_addresses:
        port_dict = network_resource.check_existing_port(
            dst_net['id'], mac_address, ip_address)
        if port_dict:
            # port_dict can be DHCP port, so there could be race condition
            # deleting this port
            with proxy_client.expect_exception(neutron_exc.NotFound):
                try:
                    network_resource.delete_port(port_dict['id'])
                except neutron_exc.NotFound:
                    pass  # Ignore ports that were deleted by neutron


def get_security_groups_ids_for_tenant(network_resource, inst, tenant_id):
    security_groups = inst[utils.INSTANCE_BODY]['security_groups']
    sg_ids = []
    for sg in network_resource.get_security_groups():
        if sg['tenant_id'] == tenant_id:
            if sg['name'] in security_groups:
                sg_ids.append(sg['id'])

    return sg_ids


def check_floating_ip(network_resource, src_net, port):
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
    return fip


def associate_floatingip(info, network_resource):
    info_compute = copy.deepcopy(info)

    instance = info_compute[utils.INSTANCES_TYPE].values()[0]
    networks_info = instance[utils.INSTANCE_BODY].get('nics', [])
    for net in networks_info:
        fip = net.get('floatingip')
        if fip is not None:
            network_resource.update_floatingip(
                fip['dst_floatingip_id'], fip['dst_port_id'])
