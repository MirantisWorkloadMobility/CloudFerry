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


import collections
from cloudferrylib.base.action import action
from cloudferrylib.utils import log
from cloudferrylib.utils import utils

LOG = log.getLogger(__name__)


class FilterSimilarVMsFromDST(action.Action):
    """
    Exclude src instances from migration workflow if they exists on dst or if
    they ip's overlaps with dst instances ip's.

    Dependencies:
        must runs after:
            - IdentityTransporter
            - GetInfoInstances
        must runs before:
            - GetInfoIter

    """
    def __init__(self, *args, **kwargs):
        super(FilterSimilarVMsFromDST, self).__init__(*args, **kwargs)
        self.src_instances = None
        self.dst_instances = {}
        self.tenant_id_to_new_id = {}
        self.skipped_instances = []
        self.similar_isntances = collections.defaultdict(set)
        self.conflict_instances = collections.defaultdict(set)

    def run(self, **kwargs):
        self.src_instances = kwargs['info']['instances']
        if 'identity_info' in kwargs:
            for tenant in kwargs['identity_info']['tenants']:
                self.tenant_id_to_new_id[tenant['tenant']['id']] = \
                    tenant['meta']['new_id']
        else:
            self.tenant_id_to_new_id = self.get_similar_tenants()
        self.find_similar_instances()
        for src_instance_id, dst_ids in self.similar_isntances.items():
            LOG.warning("Instance %s already in DST cloud as instance %s. "
                        "It will be excluded from migration.",
                        src_instance_id, dst_ids)
            self.src_instances.pop(src_instance_id)
        for src_instance_id, dst_ids in self.conflict_instances.items():
            LOG.warning("Instance %s can not be migrated to DST because "
                        "instance %s already use the same IP. "
                        "It will be excluded from migration.",
                        src_instance_id, dst_ids)
            self.src_instances.pop(src_instance_id)
        for src_instance_id in set(self.skipped_instances):
            instance = self.src_instances.pop(src_instance_id)
            LOG.warning("Instance %s can not be migrated to DST because "
                        "instance was booted in deleted tenant %s",
                        src_instance_id,
                        instance['instance']['tenant_id'])

    def find_similar_instances(self):
        # titii = tenant & ip to instance id
        #         {<tenant_id>: {<ip>: <instance_id>}}
        titii_src = self.make_tenant_ip_to_instance_id_dict(self.src_instances)
        compute_resource = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]
        for tenant_id in titii_src:
            if tenant_id in self.tenant_id_to_new_id:
                self.dst_instances.update(compute_resource.read_info(
                    tenant_id=[self.tenant_id_to_new_id[tenant_id]]
                )['instances'])
        titii_dst = self.make_tenant_ip_to_instance_id_dict(self.dst_instances)
        for tenant_id, ip_to_id in titii_src.items():
            tenant_new_id = self.tenant_id_to_new_id.get(tenant_id, None)
            if tenant_new_id is None:
                self.skipped_instances.extend(ip_to_id.values())
                continue
            dst_ip_to_id = titii_dst[tenant_new_id]
            for ip, instance_id in ip_to_id.items():
                if ip in dst_ip_to_id:
                    self.instance_comparison(instance_id, dst_ip_to_id[ip])

    @staticmethod
    def make_tenant_ip_to_instance_id_dict(instances):
        tenant_ip_to_instance_id = collections.defaultdict(dict)
        for instance in instances.values():
            info = instance['instance']
            ip_to_id = tenant_ip_to_instance_id[info['tenant_id']]
            instance_id = info['id']
            for interface in info['interfaces']:
                for ip_address in interface['ip_addresses']:
                    ip_to_id[ip_address] = instance_id
        return tenant_ip_to_instance_id

    def instance_comparison(self, src_instance_id, dst_instance_id):
        src_instance = Instance(self.src_instances[src_instance_id])
        dst_instance = Instance(self.dst_instances[dst_instance_id])
        if src_instance == dst_instance:
            self.similar_isntances[src_instance_id].add(dst_instance_id)
        else:
            self.conflict_instances[src_instance_id].add(dst_instance_id)


class Instance(object):
    COMPARISON_FIELDS = ['name', 'flav_details', 'key_name', 'interfaces',
                         'volumes']

    def __init__(self, instance):
        self.instance = instance

    def __eq__(self, other):
        for field in self.COMPARISON_FIELDS:
            if (self.instance['instance'][field] !=
                    other.instance['instance'][field]):
                return False
        return True
