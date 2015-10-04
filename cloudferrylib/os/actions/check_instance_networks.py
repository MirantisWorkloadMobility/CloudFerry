# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import ipaddr
import exceptions

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class CheckInstanceNetworks(action.Action):
    """
    verifies there are no VMs spawned directly in external network
    """

    def run(self, **kwargs):
        search_opts = kwargs.get('search_opts_tenant', {})
        network_resource = self.cloud.resources[utils.NETWORK_RESOURCE]
        networks_info = network_resource.read_info(**search_opts)
        external_networks = []
        for subnet_info in networks_info['subnets']:
            if subnet_info['external']:
                external_networks.append(ipaddr.IPNetwork(subnet_info['cidr']))
        if len(external_networks) == 0:
            return
        compute_resource = self.cloud.resources[utils.COMPUTE_RESOURCE]
        computes_info = compute_resource.read_info(**search_opts)
        instance_names = []
        for compute_info in computes_info['instances'].values():
            for interface in compute_info['instance']['interfaces']:
                addr = ipaddr.IPAddress(interface['ip'])
                for network in external_networks:
                    if network.Contains(addr):
                        instance_names.append(compute_info['instance']['name'])

        if len(instance_names) > 0:
            raise exceptions.EnvironmentError(
                "Instances %s spawned "
                "in external network directly. CloudFerry can't "
                "migrate it." % ", ".join(instance_names))
