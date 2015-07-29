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
                port_id = network_resource.check_existing_port(dst_net['id'],
                                                               src_net['mac'])
                if port_id:
                    network_resource.delete_port(port_id)
                sg_ids = []
                for sg in network_resource.get_security_groups():
                    if sg['tenant_id'] == tenant_id:
                        if sg['name'] in security_groups:
                            sg_ids.append(sg['id'])
                try:
                    port = network_resource.create_port(dst_net['id'],
                                                        src_net['mac'],
                                                        src_net['ip'],
                                                        tenant_id,
                                                        keep_ip,
                                                        sg_ids)
                except neutronclient_exceptions.IpAddressInUseClient:
                    LOG.warning("IP address '%s' on destination net '%s (%s)' "
                                "already exists!",
                                src_net['ip'], dst_net['name'], dst_net['id'])
                    continue
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
