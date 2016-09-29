# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
import logging

from neutronclient.common import exceptions as neutron_exceptions

from cloudferry import discover
from cloudferry import model
from cloudferry.model import identity
from cloudferry.model import network
from cloudferry.lib.os import clients

LOG = logging.getLogger(__name__)


class BaseNeutronDiscoverer(discover.Discoverer):
    raw_identifier = 'id'

    @abc.abstractmethod
    def list(self, network_client):
        return []

    @abc.abstractmethod
    def get(self, network_client, uuid):
        return

    @staticmethod
    def _list(fn, envelope):
        return clients.retry(fn)[envelope]

    @staticmethod
    def _get(fn, uuid, envelope):
        return clients.retry(
            fn, uuid,
            expected_exceptions=[neutron_exceptions.NotFound])[envelope]

    def discover_all(self):
        network_client = clients.network_client(self.cloud)
        for raw_object in self.list(network_client):
            try:
                with model.Session() as session:
                    session.store(self.load_from_cloud(raw_object))
            except model.ValidationError as e:
                obj_name = self.discovered_class.__name__
                id_attr = self.raw_identifier
                LOG.warning('Invalid %s %s in cloud %s: %s', obj_name,
                            raw_object[id_attr], self.cloud.name, e)

    def discover_one(self, uuid):
        network_client = clients.network_client(self.cloud)
        try:
            raw_object = self.get(network_client, uuid)
            with model.Session() as session:
                obj = self.load_from_cloud(raw_object)
                session.store(obj)
                return obj
        except neutron_exceptions.NotFound:
            raise discover.NotFound()


class NetworkDiscoverer(BaseNeutronDiscoverer):
    discovered_class = network.Network

    def list(self, network_client):
        return [n for n in
                self._list(network_client.list_networks, 'networks')
                if n['tenant_id']]

    def get(self, network_client, uuid):
        net = self._get(network_client.show_network, uuid, 'network')
        if not net['tenant_id']:
            raise discover.NotFound()
        return net

    def load_from_cloud(self, data):
        net_dict = {
            'object_id': self.make_id(data['id']),
            'tenant': self.find_ref(identity.Tenant, data['tenant_id']),
            'name': data['name'],
            'is_external': data.get('router:external', False),
            'is_shared': data['shared'],
            'admin_state_up': data['admin_state_up'],
            'status': data['status'],
            'physical_network': data['provider:physical_network'],
            'network_type': data['provider:network_type'],
            'segmentation_id': data['provider:segmentation_id'],
        }
        return network.Network.load(net_dict)


class SubnetDiscoverer(BaseNeutronDiscoverer):
    discovered_class = network.Subnet

    def list(self, network_client):
        return [sn for sn in
                self._list(network_client.list_subnets, 'subnets')
                if sn['tenant_id']]

    def get(self, network_client, uuid):
        subnet = self._get(network_client.show_subnet, uuid, 'subnet')
        if not subnet['tenant_id']:
            raise discover.NotFound()
        return subnet

    def load_from_cloud(self, data):
        subnet_dict = {
            'object_id': self.make_id(data['id']),
            'tenant': self.find_ref(identity.Tenant, data['tenant_id']),
            'network': self.find_ref(network.Network, data['network_id']),
            'name': data['name'],
            'enable_dhcp': data['enable_dhcp'],
            'dns_nameservers': data['dns_nameservers'],
            'host_routes': data['host_routes'],
            'ip_version': data['ip_version'],
            'gateway_ip': data['gateway_ip'],
            'cidr': data['cidr'],
            'allocation_pools': data['allocation_pools'],
        }
        return network.Subnet.load(subnet_dict)


class QuotaDiscoverer(BaseNeutronDiscoverer):
    discovered_class = network.Quota
    raw_identifier = 'tenant_id'

    def list(self, network_client):
        return self._list(network_client.list_quotas, 'quotas')

    def get(self, network_client, uuid):
        return self._get(network_client.show_quota, uuid, 'quota')

    def load_from_cloud(self, data):
        quota_dict = {
            'object_id': self.make_id(data['tenant_id']),
            'tenant': self.find_ref(identity.Tenant, data['tenant_id']),
            'floatingip': data['floatingip'],
            'network': data['network'],
            'port': data['port'],
            'router': data['router'],
            'security_group': data['security_group'],
            'security_group_rule': data['security_group_rule'],
            'subnet': data['subnet'],
        }
        return network.Quota.load(quota_dict)
