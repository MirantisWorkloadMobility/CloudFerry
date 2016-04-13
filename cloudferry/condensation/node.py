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

import math
import copy

from oslo_config import cfg

from cloudferry.condensation import algorithms


CONF = cfg.CONF


class Node(object):

    """This  class is representation of physical server"""

    def __init__(self, name, core, ram, core_ratio, ram_ratio,
                 ram_factor, core_factor):
        self.name = name
        self.core = int(
            math.floor(core * core_ratio / CONF.condense.core_reduction_coef))
        self.ram = int(
            math.floor(ram * ram_ratio / CONF.condense.ram_reduction_coef))
        self.ram_factor = ram_factor
        self.core_factor = core_factor
        self.vms = {}

    def link_vm(self, vm_obj):
        """
            This method adds vm to dict
        """
        self.vms.update({vm_obj.vm_id: vm_obj})

    def unlink_vm(self, vm_obj):
        """
            This method removes vm from dict
        """
        if vm_obj.vm_id in self.vms:
            del self.vms[vm_obj.vm_id]

    def get_vm_by_flavor(self, flavor):
        """
            Returns vm with flavor provided from this node
        """
        for vm_obj in self.vms.values():
            if vm_obj.flavor == flavor:
                return vm_obj

    @property
    def is_full(self):
        """
            Checks if node is full
        """
        return max(self.utilization) > CONF.condense.precision

    @property
    def free_resources(self):
        """
            This method returns free ram, core on Node
        """
        return (self.ram - sum(i.flavor.ram for k, i in self.vms.items()),
                self.core - sum(i.flavor.core for k, i in self.vms.items()))

    @property
    def utilization(self):
        """
            This method returns percentage of ram, core usage
        """
        free_ram, free_core = self.free_resources
        return ((self.ram - free_ram) * 100. / self.ram,
                (self.core - free_core) * 100. / self.core)

    def potential_utilization(self, flavors):
        """
            This method returns percentage of ram, core usage in case
            we gonna migrate provided flavors to the node
        """
        free_ram, free_core = self.free_resources
        for fl_obj, count in flavors.items():
            free_ram -= fl_obj.ram * count
            free_core -= fl_obj.core * count
        return ((self.ram - free_ram) * 100. / self.ram,
                (self.core - free_core) * 100. / self.core)

    def calculate_flavors_required(self, flavors, accurate=False):
        """
        This method calculates how much vms of different flavors do we need
        to full this node
        It uses 2 different algorithms:
            1) "ACCURATE" - classic bounded multidimensional multiobjective
                            knapsack problem
                            We need this algorithm in the end of condensation
                            phase. Because it complexity hardly depends on
                            number of vms that are not on full nodes
            2) "FAST" - modified unbounded multidimensinal multiobjective
                        problem.
                        We need this algorithm at the begining of condensation
                        to speed up the process. It complexity depends on
                        number of flavors that is always less than number of
                        vms
        """
        # reduce count of flavors
        # we need this step to reduce number of available flavors
        # because we have vms assigned to this node
        flavors = copy.copy(flavors)
        for value in self.vms.values():
            if value.flavor in flavors:
                flavors[value.flavor] -= 1

        # as soon as we reduced complexity of our problem by common factor
        # of ram and cpus - we need to recalculate available ram and cores
        # by new scale
        # count max core and max ram
        free_resources = self.free_resources
        max_core = int(math.floor(free_resources[1] / self.core_factor))
        max_ram = int(math.floor(free_resources[0] / self.ram_factor))

        flavors_dict = {}
        flavors_list = []
        result_dict = {}
        if accurate:
            # convert data from dict to list of tuples (algorithm interface)
            flavor_id, flavor_ram = (0, 1)
            for fl_obj, count in flavors.items():
                flavors_dict[fl_obj.fl_id] = fl_obj
                for i in range(count):
                    flavors_list.append(
                        (fl_obj.fl_id,
                         fl_obj.reduced_ram, fl_obj.reduced_core))
            # convert output of algorithm to application interface (dict)
            for i in algorithms.accurate(flavors_list, max_ram, max_core):
                flavor = flavors_dict[i[flavor_id]]
                if flavor not in result_dict:
                    result_dict[flavor] = 0
                result_dict[flavor] += 1
        else:
            # use fast algorithm
            # convert data from dict to list of tuples (algorithm interface)
            flavor_id, flavor_ram = (0, 2)
            # transform flavors to more comfortable datatype
            for fl_obj, count in flavors.items():
                flavors_dict[fl_obj.fl_id] = fl_obj
                flavors_list.append(
                    (fl_obj.fl_id, count, fl_obj.reduced_ram,
                     fl_obj.reduced_core))
            # sort flavors by ram
            flavors_list = sorted(flavors_list, key=lambda a: a[flavor_ram],
                                  reverse=True)
            # convert solution from list data structure to dict
            for index, i in enumerate(algorithms.fast(
                    flavors_list, max_ram, max_core)):
                if i:
                    flavor = flavors_dict[flavors_list[index][flavor_id]]
                    if flavor not in result_dict:
                        result_dict[flavor] = 0
                    result_dict[flavor] += i
        return result_dict
