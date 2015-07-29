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

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class AssociateFloatingip(action.Action):
    """Associates previously created VM port with floating IP port

    Depends on:
     - Identity objects migrated
     - Instance ports migrated (see `PrepareNetworks`)
     - Network objects migrated, primarily floating IPs
    """

    def run(self, info=None, **kwargs):
        if self.cfg.migrate.keep_floatingip:
            info_compute = copy.deepcopy(info)
            network_resource = self.cloud.resources[utl.NETWORK_RESOURCE]

            instance = info_compute[utl.INSTANCES_TYPE].values()[0]
            networks_info = instance[utl.INSTANCE_BODY].get('nics', [])
            for net in networks_info:
                fip = net.get('floatingip')
                if fip is not None:
                    network_resource.update_floatingip(
                        fip['dst_floatingip_id'], fip['dst_port_id'])
        return {}


class DisassociateFloatingip(action.Action):
    """Disassociates floating IP from VM"""

    def run(self, info=None, **kwargs):
        if self.cfg.migrate.keep_floatingip:
            info_compute = copy.deepcopy(info)
            compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]

            instance = info_compute[utl.INSTANCES_TYPE].values()[0]

            networks_info = instance[utl.INSTANCE_BODY][utl.INTERFACES]
            old_id = instance[utl.OLD_ID]
            for net in networks_info:
                if net['floatingip']:
                    compute_resource.dissociate_floatingip(old_id,
                                                           net['floatingip'])
        return {}


class DisassociateAllFloatingips(action.Action):
    """Disassociates all floating IPs from VM on source"""

    def run(self, info=None, **kwargs):
        if self.cfg.migrate.keep_floatingip:
            info_compute = copy.deepcopy(info)
            compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]

            instances = info_compute[utl.INSTANCES_TYPE]

            for instance in instances.values():
                networks_info = instance[utl.INSTANCE_BODY][utl.INTERFACES]
                old_id = instance[utl.OLD_ID]
                for net in networks_info:
                    if net['floatingip']:
                        compute_resource.dissociate_floatingip(
                            old_id, net['floatingip'])
        return {}
