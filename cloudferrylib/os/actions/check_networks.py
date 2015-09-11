# Copyright (c) 2015 Mirantis Inc.
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

import ipaddr
import collections
import exceptions
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class CheckNetworks(action.Action):
    """
    Check subnets overlapping and raise EnvironmentError if needed.
    It must be done before actual migration in check section.
    The action use filter search opts and must run after act_get_filter action
    """

    def run(self, **kwargs):
        LOG.debug("Start 'check_networks' action")
        src_net = self.src_cloud.resources[utils.NETWORK_RESOURCE]
        dst_net = self.dst_cloud.resources[utils.NETWORK_RESOURCE]
        search_opts = kwargs.get('search_opts_tenant', {})
        src_info = NetworkInfo(src_net.read_info(**search_opts))
        dst_info = NetworkInfo(dst_net.read_info(**search_opts))
        for network in src_info.get_networks():
            dst_net = dst_info.by_hash.get(network.hash)
            if dst_net:
                LOG.debug("src network %s, dst network %s" %
                          (network.id, dst_net.id))
                network.check_network_overlapping(dst_net)


class NetworkInfo(object):
    def __init__(self, info):
        self.by_id = {}
        self.by_hash = collections.defaultdict()
        for net_map in info['networks']:
            network = Network(net_map)
            self.by_id[network.id] = network
            self.by_hash[network.hash] = network
        for subnet in info['subnets']:
            network = self.by_id[subnet['network_id']]
            network.add_subnet(subnet)

    def get_networks(self):
        return self.by_hash.values()


class Network(object):
    def __init__(self, info):
        self.info = info
        self.subnets_hash = set()
        self.subnets = []
        self.id = info['id']
        self.hash = info['res_hash']

    def add_subnet(self, info):
        self.subnets.append(info)
        self.subnets_hash.add(info['res_hash'])

    def check_network_overlapping(self, network):
        for subnet in network.subnets:
            LOG.debug("work on src subnet %s" % subnet['id'])
            if self.is_subnet_eq(subnet):
                LOG.debug("We have the same on dst by hash")
                continue
            overlapping_subnet = self.get_overlapping_subnet(subnet)
            if overlapping_subnet:
                message = ("Subnet %s in network %s on src overlap "
                           "subnet %s in network %s on dst" % (
                                overlapping_subnet, self.id,
                                subnet['id'], network.id))
                LOG.error(message)
                raise exceptions.EnvironmentError(message)

    def is_subnet_eq(self, subnet):
        return subnet['res_hash'] in self.subnets_hash

    def get_overlapping_subnet(self, subnet):
        cidr = ipaddr.IPNetwork(subnet['cidr'])
        for self_subnet in self.subnets:
            self_cidr = ipaddr.IPNetwork(self_subnet['cidr'])
            if (cidr.Contains(self_cidr) or self_cidr.Contains(cidr)):
                return self_subnet['id']
