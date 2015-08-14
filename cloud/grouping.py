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


import cloud

from cloudferrylib.os.identity import keystone
from cloudferrylib.os.network import neutron
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class Grouping(object):
    def __init__(self, config, group_file, cloud_id):
        self.config = config
        if group_file is None:
            message = "Grouping config is not provided."
            LOG.error(message)
            raise ValueError(message)
        self.group_config = utils.read_yaml_file(group_file)
        resources = {'identity': keystone.KeystoneIdentity,
                     'network': neutron.NeutronNetwork,
                     'compute': nova_compute.NovaCompute}
        self.cloud = cloud.Cloud(resources, cloud_id, config)

        self.network = self.cloud.resources['network']
        self.compute = self.cloud.resources['compute']
        self.identity = self.cloud.resources['identity']

        self.groups = {}

    def group(self, validate=False):
        group_by = self.group_config.pop('group_by')

        for step, grouping in enumerate(group_by):
            groups = self._group_by(grouping, step)
            if not step:
                self.groups = groups

        self._walk(self.groups, self._normalize)
        self._make_users_group(self.groups, validate=validate)

        utils.write_yaml_file(self.config.migrate.group_file_path, self.groups)

    def _group_by(self, target, step):
        group_rules_map = {'tenant': self._group_nested_tenant,
                           'network': self._group_nested_network,
                           }
        group_func = group_rules_map.get(target)

        if not group_func:
            raise RuntimeError("There is no such grouping option. Use 'tenant'"
                               " or 'network' values in the 'group_by' section"
                               " of the group config file")

        if not step:
            return group_func()
        else:
            self._walk(self.groups, group_func)
            return self.groups

    def _group_nested_tenant(self, instances_list=None):
        groups = {}

        tenant_list = self.identity.get_tenants_list()
        search_list = (instances_list if instances_list else
                       self.compute.get_instances_list(
                           search_opts={"all_tenants": True}))
        for tenant in tenant_list:
            LOG.info('Processing tenant %s', tenant.id)
            groups[str(tenant.id)] = [vm for vm in search_list
                                      if vm.tenant_id == tenant.id]

        return groups

    def _group_nested_network(self, instances_list=None):
        groups = {}

        search_list = (instances_list if instances_list else
                       self.compute.get_instances_list(
                           search_opts={"all_tenants": True}))
        for instance in search_list:
            LOG.info('Processing instance %s', instance.name)
            for (network_name, network_ips) in instance.networks.items():
                network = self.network.get_network({'ip': network_ips[0]},
                                                   instance.tenant_id,
                                                   True)
                network_id = network['id']
                if network_id in groups:
                    groups[network_id].append(instance)
                else:
                    groups[network_id] = [instance]

        return groups

    def _make_users_group(self, static_group, validate):
        vms = self.group_config.values()
        user_defined_vms = reduce(lambda res, x: x + res, vms, [])

        if validate:
            user_defined_vms = filter(self.compute.is_nova_instance,
                                      user_defined_vms)
            # remove duplicates
            for user_group, vms_list in self.group_config.items():
                self.group_config[user_group] = [vm for vm in set(vms_list)
                                                 if vm in user_defined_vms]

        self._walk_user_defined(static_group, user_defined_vms)

        static_group.update(self.group_config)

    def _walk(self, groups, nested_func):
        for key, value in groups.items():
            if isinstance(value, dict):
                self._walk(value, nested_func)
            else:
                if not value:
                    # exclude empty groups
                    groups.pop(key)
                    continue

                groups[key] = nested_func(value)

    def _walk_user_defined(self, groups, user_vms):
        for key, value in groups.items():
            if isinstance(value, dict):
                self._walk_user_defined(value, user_vms)
            else:
                if value:
                    same = set(value) & set(user_vms)
                    [value.remove(i) for i in same if i in value]

    @staticmethod
    def _normalize(instance_list):
        return [str(instance.id) for instance in instance_list]
