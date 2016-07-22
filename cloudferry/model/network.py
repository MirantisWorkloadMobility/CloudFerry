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

from cloudferry import model
from cloudferry.model import identity


@model.type_alias('network_quotas')
class Quota(model.Model):
    object_id = model.PrimaryKey()
    tenant = model.Dependency(identity.Tenant)
    floatingip = model.Integer(required=True)
    network = model.Integer(required=True)
    port = model.Integer(required=True)
    router = model.Integer(required=True)
    security_group = model.Integer(required=True)
    security_group_rule = model.Integer(required=True)
    subnet = model.Integer(required=True)

    def equals(self, other):
        # pylint: disable=no-member
        if super(Quota, self).equals(other):
            return True
        return self.tenant.equals(other.tenant) \
            and self.floatingip == other.floatingip \
            and self.network == other.network \
            and self.port == other.port \
            and self.router == other.router \
            and self.security_group == other.security_group \
            and self.security_group_rule == other.security_group_rule \
            and self.subnet == other.subnet


@model.type_alias('networks')
class Network(model.Model):
    object_id = model.PrimaryKey()
    tenant = model.Dependency(identity.Tenant)
    name = model.String(required=True)
    is_external = model.Boolean(required=True)
    is_shared = model.Boolean(required=True)
    admin_state_up = model.Boolean(required=True)
    status = model.String(required=True)
    physical_network = model.String(required=True, allow_none=True)
    network_type = model.String(required=True)
    segmentation_id = model.Integer(required=True)
    subnets = model.Reference('cloudferry.model.network.Subnet', many=True,
                              missing=[])

    def equals(self, other):
        # pylint: disable=no-member,not-an-iterable
        if super(Network, self).equals(other):
            return True

        if len(self.subnets) != len(other.subnets):
            return False
        for subnet1 in self.subnets:
            for subnet2 in other.subnets:
                if subnet1.equals(subnet2):
                    break
            else:
                return False

        return self.tenant.equals(other.tenant) and \
            self.name == other.name and \
            self.is_external == other.is_external and \
            self.is_shared == other.is_shared and \
            self.admin_state_up == other.admin_state_up and \
            self.status == other.status and \
            self.physical_network == other.physical_network and \
            self.network_type == other.network_type


class AllocationPool(model.Model):
    start = model.String(required=True)
    end = model.String(required=True)

    def equals(self, other):
        return self.start == other.start and self.end == other.end


@model.type_alias('subnets')
class Subnet(model.Model):
    object_id = model.PrimaryKey()
    network = model.Dependency(Network, required=True, backref='subnets')
    tenant = model.Dependency(identity.Tenant)
    name = model.String(required=True)
    enable_dhcp = model.Boolean(required=True)
    dns_nameservers = model.List(model.String(), missing=list)
    allocation_pools = model.Nested(AllocationPool, many=True)
    host_routes = model.List(model.String(), missing=list)
    ip_version = model.Integer(required=True)
    gateway_ip = model.String(required=True, allow_none=True)
    cidr = model.String(required=True)

    def equals(self, other):
        # pylint: disable=no-member,not-an-iterable
        if super(Subnet, self).equals(other):
            return True
        if len(self.allocation_pools) != len(other.allocation_pools):
            return False
        for allocation_pool1 in self.allocation_pools:
            for allocation_pool2 in other.allocation_pools:
                if allocation_pool1.equals(allocation_pool2):
                    break
            else:
                return False

        return self.network.equals(other.network) and \
            self.tenant.equals(other.tenant) and \
            self.cidr == other.cidr and \
            self.ip_version == other.ip_version


class Port(model.Model):
    pass


class Router(model.Model):
    pass


class FloatingIp(model.Model):
    pass
