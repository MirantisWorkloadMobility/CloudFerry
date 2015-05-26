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

import uuid


class Flavor(object):

    """This class is representation of OpenStack flavor"""

    def __init__(self, fl_id, name, ram, core, ephemeral=None, swap=None):
        self.fl_id = fl_id
        self.name = name
        self.ram = ram
        self.core = core
        self.ephemeral = ephemeral
        self.swap = swap
        self.vms = []
        self.reduced_ram = None
        self.reduced_core = None

    def reduce_resources(self, ram_factor, core_factor):
        """
        We need to reduce complexity of the problem in all possible ways
        As soon as we deal with flavors - we have to keep in mind that we can
        count flavors http://en.wikipedia.org/wiki/Greatest_common_divisor
        for ram and core
        and reduce complexity when calculating distribution of flavors over
        nodes with dynamic programming techinque
        """
        self.reduced_ram = self.ram / ram_factor
        self.reduced_core = self.core / core_factor

    def link_vm(self, vm_obj):
        """
            This method links vm from args to particular flavor
        """
        self.vms.append(vm_obj)

    def amount(self, cloud):
        """
        This method returns how much vms with flavor exist on nodes that
        are not full
        """
        return len([i for i in self.vms if (
            not i.node.is_full and i.node.cloud == cloud)])

    def node_distribution(self, cloud):
        """
        This method returns dict of nodes that contains this flavor
        with number of vms with flavor as value
        """
        result = {}
        for vm_obj in self.vms:
            if not vm_obj.node.is_full and vm_obj.node.cloud == cloud:
                if vm_obj.node not in result:
                    result[vm_obj.node] = 0
                result[vm_obj.node] += 1
        return result

    @classmethod
    def default(cls, flavor_id=str(uuid.uuid4())):
        """
        In case flavor is not available for a VM (flavor was deleted after VM
        is spawned), this method generates 'default' flavor. Currently all the
        values are hardcoded."""
        return cls(fl_id=flavor_id,
                   name="default-condensation-flavor",
                   ram=4096,
                   core=2)

    def __repr__(self):
        return "%s [%s]" % (self.name, self.fl_id)


default = Flavor.default()
