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


import collections

import ipaddr

from cloudferrylib.base import exception
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class CheckNetworks(action.Action):
    """
    Check networks segmentation ID, subnets and floating IPs overlapping. Also
    check if VMs from SRC spawned in external networks directly.

    Returns list of all overlaps and prints it to the LOG. If this list is
    non-empty, raise exception (AbortMigrationError).

    It must be done before actual migration in the 'preparation' section.
    The action uses filtered search opts and must be run after 'act_get_filter'
    action.
    """

    def run(self, **kwargs):
        LOG.debug("Checking networks...")
        overlapped_resources = {}

        src_net = self.src_cloud.resources[utils.NETWORK_RESOURCE]
        dst_net = self.dst_cloud.resources[utils.NETWORK_RESOURCE]
        src_compute = self.src_cloud.resources[utils.COMPUTE_RESOURCE]

        search_opts = kwargs.get('search_opts_tenant', {})
        search_opts.update({'search_opts': kwargs.get('search_opts', {})})

        LOG.debug("Retrieving Network information from Source cloud...")
        src_net_info = NetworkInfo(src_net.read_info(**search_opts))
        LOG.debug("Retrieving Network information from Destination cloud...")
        dst_net_info = NetworkInfo(dst_net.read_info())
        LOG.debug("Retrieving Compute information from Source cloud...")
        src_compute_info = ComputeInfo(src_compute.read_info(**search_opts))

        # Check subnets and segmentation IDs overlap
        LOG.info("Check networks overlapping...")
        nets_overlapped_subnets, nets_overlapped_seg_ids = (
            src_net_info.get_overlapped_networks(dst_net_info))
        if nets_overlapped_subnets:
            overlapped_resources.update(
                {'networks_with_overlapped_subnets': nets_overlapped_subnets})
        if nets_overlapped_seg_ids:
            overlapped_resources.update(
                {'networks_with_overlapped_segm_ids': nets_overlapped_seg_ids})

        # Check floating IPs overlap
        LOG.info("Check floating IPs overlapping...")
        floating_ips = src_net_info.list_overlapped_floating_ips(dst_net_info)
        if floating_ips:
            overlapped_resources.update(
                {'overlapped_floating_ips': floating_ips})

        # Check VMs spawned directly in external network
        LOG.info("Check VMs spawned directly in external networks...")
        ext_nets = src_net_info.get_external_networks()
        vms_list = src_compute_info.list_vms_in_external_network(ext_nets)
        if vms_list:
            overlapped_resources.update({'vms_in_external_network': vms_list})

        # Print LOG message with all overlapped stuff and abort migration
        if overlapped_resources:
            LOG.critical('Network overlapping list:\n%s', overlapped_resources)
            raise exception.AbortMigrationError(
                "There is a number of overlapping Network resources, so "
                "migration process can not be continued. Resolve it please and"
                " try again.")


class ComputeInfo(object):
    def __init__(self, info):
        self.instances = {}
        for instance_id, instance_map in info['instances'].iteritems():
            instance = Compute(instance_map)
            self.instances[instance_id] = instance

    def list_vms_in_external_network(self, external_networks):
        """
        Get list of VMs IDs, that are spawned in external network directly.

        :param external_networks: List of ipaddr.IPNetwork instances of ext net
        :return list:
        """
        if not external_networks:
            LOG.debug('There are no external networks on the SRC cloud. '
                      'Finishing check.')
            return

        result_instances = []
        for instance in self.instances.values():
            if instance.is_instance_in_external_network(external_networks):
                result_instances.append(instance.id)

        # remove duplicates, cause 1 VM can be spawned in several external nets
        result_instances = list(set(result_instances))

        return result_instances


class Compute(object):
    def __init__(self, info):
        self.interfaces = info['instance']['interfaces']
        self.id = info['instance']['id']

    def is_instance_in_external_network(self, external_networks):
        """
        Check if Nova VM spawned in external network directly.

        :param external_networks: List of ipaddr.IPNetwork instances of ext net
        :return bool:
        """

        for interface in self.interfaces:
            ip = ipaddr.IPAddress(interface['ip'])
            for network in external_networks:
                if network.Contains(ip):
                    LOG.error("Instance %s has been spawned in external "
                              "network directly.", self.id)
                    return True
        return False


class NetworkInfo(object):
    def __init__(self, info):
        self.by_id = {}
        self.by_hash = collections.defaultdict()
        self.subnets = info['subnets']
        self.floating_ips = {}
        for net_map in info['networks']:
            network = Network(net_map)
            self.by_id[network.id] = network
            self.by_hash[network.hash] = network
        for subnet in self.subnets:
            network = self.by_id[subnet['network_id']]
            network.add_subnet(subnet)
        for floating_ip_map in info['floating_ips']:
            floating_ip = FloatingIp(floating_ip_map)
            self.floating_ips[floating_ip.address] = floating_ip

    def get_networks(self):
        return self.by_id.values()

    def get_network_by_segmentation_id(self, net_type, segmentation_id):
        """
        Get network by it's type and segmentation ID.

        :param net_type: Network type (f.e. gre, vlan, etc.)
        :param segmentation_id: Segmentation ID

        :result: Network instance, that fits with requirements
        """

        for net in self.get_networks():
            if net.network_type == net_type and net.seg_id == segmentation_id:
                return net

    def get_segmentation_ids(self):
        """Get busy segmentation IDs.

        We need to handle duplicates in segmentation ids.
        Neutron has different validation rules for different network types.

        For 'gre' and 'vxlan' network types there is no strong requirement
        for 'physical_network' attribute, if we want to have
        'segmentation_id', because traffic is encapsulated in L3 packets.

        For 'vlan' and 'flat' network types there is a strong requirement for
        'physical_network' attribute, if we want to have 'segmentation_id'.

        :result: Dictionary with busy segmentation IDs.
                 Hash is used with structure {"gre": [1, 2, ...],
                                              "vlan": [1, 2, ...]}
        """

        used_seg_ids = {}
        networks = self.get_networks()

        for net in networks:
            network_has_segmentation_id = (
                net.info["provider:physical_network"] or
                (net.network_type in ['gre', 'vxlan']))

            if network_has_segmentation_id:
                if net.network_type not in used_seg_ids:
                    used_seg_ids[net.network_type] = []
                if net.seg_id:
                    used_seg_ids[net.network_type].append(net.seg_id)

        return used_seg_ids

    def get_external_networks(self):
        """
        Get list of external networks.

        :return list: List of ipaddr.IPNetwork instances of external networks
        """

        external_networks = []
        for subnet in self.subnets:
            if subnet['external']:
                external_networks.append(ipaddr.IPNetwork(subnet['cidr']))
        return external_networks

    def list_overlapped_floating_ips(self, dst_info):
        """
        Get list of Floating IPs, that overlap with the DST.

        :param dst_info: NetworkInfo instance of DST cloud
        """

        floating_ips_list = []

        for floating_ip in self.floating_ips.values():
            dst_floating_ip = dst_info.floating_ips.get(floating_ip.address)
            if not dst_floating_ip:
                LOG.debug("There is no such Floating IP on DST: '%s'. "
                          "Continue...", floating_ip.address)
                continue

            LOG.debug('Floating IP `%s` has been found on DST. Checking for '
                      'overlap...', floating_ip.address)
            try:
                floating_ip.check_floating_ips_overlapping(dst_floating_ip)
            except exception.AbortMigrationError:
                floating_ips_list.append(floating_ip.address)

        return floating_ips_list

    def get_overlapped_networks(self, dst_info):
        """
        Get lists of networks, that overlap with the DST.

        :param dst_info: NetworkInfo instance of DST cloud

        :return nets_with_overlapped_subnets, nets_with_overlapped_seg_ids:
            Tuple of lists with overlapped networks IDs.
             1. List of networks IDs with overlapped subnets;
             2. List of networks IDs with overlapped segmentation IDs.
        """

        dst_seg_ids = dst_info.get_segmentation_ids()
        nets_with_overlapped_subnets = []
        nets_with_overlapped_seg_ids = []

        for network in self.get_networks():
            dst_net = dst_info.by_hash.get(network.hash)
            if dst_net:
                # Current network matches with network on DST
                # Have the same networks on SRC and DST
                LOG.debug("SRC network: '%s', DST network: '%s'" %
                          (network.id, dst_net.id))
                try:
                    network.check_network_overlapping(dst_net)
                except exception.AbortMigrationError:
                    nets_with_overlapped_subnets.append(network.id)
            else:
                # Current network does not match with any network on DST
                # Check Segmentation ID overlapping with DST
                LOG.debug("Check segmentation ID for SRC network: '%s'",
                          network.id)
                try:
                    network.check_segmentation_id_overlapping(dst_seg_ids)
                except exception.AbortMigrationError:
                    dst_network = dst_info.get_network_by_segmentation_id(
                        network.network_type, network.seg_id)
                    overlap = {'src_net_id': network.id,
                               'dst_net_id': dst_network.id}
                    nets_with_overlapped_seg_ids.append(overlap)

        # remove duplicates, cause 1 net may have several overlapped subnets
        nets_with_overlapped_subnets = list(set(nets_with_overlapped_subnets))

        return nets_with_overlapped_subnets, nets_with_overlapped_seg_ids


class Network(object):
    def __init__(self, info):
        self.info = info
        self.subnets_hash = set()
        self.subnets = []
        self.id = info['id']
        self.hash = info['res_hash']

        self.network_type = self.info['provider:network_type']
        self.seg_id = self.info["provider:segmentation_id"]

    def add_subnet(self, info):
        self.subnets.append(info)
        self.subnets_hash.add(info['res_hash'])

    def check_network_overlapping(self, network):
        for subnet in network.subnets:
            LOG.debug("Work with SRC subnet: '%s'" % subnet['id'])
            if self.is_subnet_eq(subnet):
                LOG.debug("We have the same subnet on DST by hash")
                continue
            overlapping_subnet = self.get_overlapping_subnet(subnet)
            if overlapping_subnet:
                message = ("Subnet '%s' in network '%s' on SRC overlaps with "
                           "subnet '%s' in network '%s' on DST" % (
                               overlapping_subnet, self.id,
                               subnet['id'], network.id))
                LOG.error(message)
                raise exception.AbortMigrationError(message)

    def is_subnet_eq(self, subnet):
        return subnet['res_hash'] in self.subnets_hash

    def get_overlapping_subnet(self, subnet):
        cidr = ipaddr.IPNetwork(subnet['cidr'])
        for self_subnet in self.subnets:
            self_cidr = ipaddr.IPNetwork(self_subnet['cidr'])
            if cidr.Contains(self_cidr) or self_cidr.Contains(cidr):
                return self_subnet['id']

    def check_segmentation_id_overlapping(self, dst_seg_ids):
        """
        Check if segmentation ID of current network overlaps with destination.

        :param dst_seg_ids: Dictionary with busy segmentation IDs on DST
        """

        if self.network_type not in dst_seg_ids:
            return

        if self.seg_id in dst_seg_ids[self.network_type]:
            message = ("Segmentation ID '%s' (network type = '%s', "
                       "network ID = '%s') is already busy on the destination "
                       "cloud.") % (self.seg_id, self.network_type, self.id)
            LOG.error(message)
            raise exception.AbortMigrationError(message)


class FloatingIp(object):
    def __init__(self, info):
        self.address = info['floating_ip_address']
        self.tenant = info['tenant_name']
        self.network = info['network_name']
        self.net_tenant = info['ext_net_tenant_name']
        self.port_id = info['port_id']

    def __eq__(self, other):
        if not isinstance(other, FloatingIp):
            return False

        return (self.address == other.address and
                self.tenant == other.tenant and
                self.network == other.network and
                self.net_tenant == other.net_tenant)

    def check_floating_ips_overlapping(self, dst_floating_ip):
        """
        Check if Floating IP overlaps with DST.

        Parameters to compare:
        - same floating ip address;
        - same tenant;
        - same network;
        - same network's tenant.

        Also check if this Floating IP is not busy (i.e. is not associated to
        VM on SRC and DST at the same time) on both environments.

        :raise AbortMigrationError: If FloatingIp overlaps with the DST.
        """

        # Check association to VMs on SRC and DST aa the same time
        ports_overlap = self.port_id and dst_floating_ip.port_id

        if not self == dst_floating_ip or ports_overlap:
            message = ("Floating IP '%s' overlaps with the same IP on DST." %
                       self.address)
            LOG.error(message)
            raise exception.AbortMigrationError(message)
