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

from condensation import group
from condensation import flavor
from condensation import action
from condensation import node
from condensation import vm

import prettytable
import fractions
from cfglib import CONF
from cloudferrylib.utils import utils
LOG = utils.get_log(__name__)


class Cloud(object):

    """This class is representation of All resources of cloud"""

    @classmethod
    def from_dicts(cls, name, nodes, flavors, vms, groups):
        """
        This method creates cloud structure from dicts parsed from files
        We create objects in following order:
            1 - create flavor objects
            2 - find http://en.wikipedia.org/wiki/Greatest_common_divisor on
                all flavor properties
            3 - call reduce_resources method on all flavors objects
            4 - create all nodes objects
            5 - create vm objects assigned linked with node objects and
                flavor objects
            6 - create group objects linked to vms
        """
        nodes_dict, flavors_dict, vms_dict = {}, {}, {}

        # create Flavor Objects
        for flavor_id, flavor_params in flavors.items():
            flavors_dict.update(
                {flavor_id: flavor.Flavor(**flavor_params)})
        flavors_dict[flavor.default] = flavor.default

        # count gcd on Flavors for ram and cores
        ram_factor = reduce(
            fractions.gcd, [i.ram for i in flavors_dict.values()])
        core_factor = reduce(
            fractions.gcd, [i.core for i in flavors_dict.values()])

        # reduce flavors with core_factor and ram_factor
        for flavor_obj in flavors_dict.values():
            flavor_obj.reduce_resources(ram_factor, core_factor)

        # create Node Objects
        for node_name, node_params in nodes.items():
            # replace fqdn with just node name
            node_name = node_name.split(".")[0]
            nodes_dict.update(
                {node_name: node.Node(
                    name=node_name,
                    ram_factor=ram_factor,
                    core_factor=core_factor,
                    **node_params)})

        # create Vm objects linked to Nodes and Flavors
        for vm_params in vms.values():
            node_obj = nodes_dict.get(vm_params.get("host"))
            if node_obj is None:
                # VM is running on a host which is down
                LOG.info("VM '%s' is running on a down host. Skipping.",
                         vm_params['id'])
                continue
            flavor_obj = flavors_dict.get(vm_params.get("flavor"))
            vms_dict.update({vm_params.get("id"): vm.Vm(
                node=node_obj,
                vm_id=vm_params.get("id"),
                flavor=flavor_obj)})

        # create Groups objects
        groups = group.Group.from_dict(groups, vms_dict)
        return cls(name, nodes_dict, groups)

    def __init__(self, name, nodes=None, groups=None):
        if not nodes:
            nodes = {}
        if not groups:
            groups = []
        self.name = name
        self.add_nodes(nodes)
        self.groups = groups
        self.required_flavors_for_nodes = {}
        self.node_ids_to_be_recalculated = []
        self.actions = action.Actions(name)
        # do we need to solve bounded dynamic knapsacks problem
        self.improve_accuracy = False
        LOG.debug("created cloud obj with name " + name)

    def add_nodes(self, nodes_dict):
        """
            This method adds nodes to self
        """
        LOG.debug("adding nodes to cloud " + self.name)
        self.nodes = nodes_dict
        for node_obj in nodes_dict.values():
            node_obj.cloud = self

    def calc_required_flavors_for_nodes(self):
        """
        This method recalculates flavor distribution over nodes for all
        node names in self.node_ids_to_be_recalculated
        This trick reduces total complexity of the program
        We don't have to recalculate distribution for all nodes
        only for ones that are in array
        """
        # we need to count for each flavor distribution
        # on nodes that are not full
        LOG.debug("starting recalculation of flavor distribution over nodes")
        flavors_dict = {}
        for node_obj in self.nodes.values():
            if node_obj.is_full:
                continue
            for vm_obj in node_obj.vms.values():
                if vm_obj.flavor not in flavors_dict:
                    flavors_dict[vm_obj.flavor] = 0
                flavors_dict[vm_obj.flavor] += 1

        # just in case - make list of nodes to be recalculated distinct
        self.node_ids_to_be_recalculated = list(set(
            self.node_ids_to_be_recalculated))
        LOG.info("recalculating nodes " + ",".join(
            self.node_ids_to_be_recalculated))
        for node_name in self.node_ids_to_be_recalculated:
            # paranoid check
            if node_name not in self.nodes:
                if node_name in self.required_flavors_for_nodes:
                    del self.required_flavors_for_nodes[node_name]
                continue
            node_obj = self.nodes[node_name]
            if node_obj.vms and not node_obj.is_full:
                LOG.debug("recalculating " + node_name)
                self.required_flavors_for_nodes.update({
                    node_name: node_obj.calculate_flavors_required(
                        flavors_dict,
                        self.improve_accuracy)})

        # after updating distribution clear list
        self.node_ids_to_be_recalculated = []
        LOG.debug("finished recalculation of flavor distribution over nodes")

    def condense(self, improve_accuracy=False):
        """
            This method finds vms distribution on nodes with highest density
            it runs recursively until we cannot find better solution
        """
        self.required_flavors_for_nodes = {}
        self.improve_accuracy = improve_accuracy
        self.node_ids_to_be_recalculated = []
        # recalculate all nodes that are neither full, nor empty
        for node_name, node_obj in self.nodes.items():
            if node_obj.vms and not node_obj.is_full:
                self.node_ids_to_be_recalculated.append(node_name)
        self.condense_recursively()

    def fil_node(self, node_to_be_filled, node_name_to_be_filled):
        for flavor_obj, count in self.required_flavors_for_nodes[
                node_name_to_be_filled].items():
            # for all nodes containing that flavor we have number of vms
            # with flavor on that node
            for node_obj, flavor_count in flavor_obj.node_distribution(
                    self).items():
                if not count:
                    # we placed enough vms of this flavor to node
                    break
                if node_obj == node_to_be_filled or node_obj.is_full:
                    # we don't have to move vm from full nodes
                    continue
                if node_obj.name not in self.node_ids_to_be_recalculated:
                    # as soon as we moved vm from the node - we need to
                    # recalculate distribution on this node
                    self.node_ids_to_be_recalculated.append(node_obj.name)
                for counter in range(flavor_count):
                    if not count:
                        # we placed enough vms of this flavor to node
                        break
                    # evacuate node from one node to another
                    vm_obj = node_obj.get_vm_by_flavor(flavor_obj)
                    vm_obj.link_node(node_to_be_filled)
                    self.actions.add_condensation_action(
                        vm_obj, node_obj, node_to_be_filled)
                    count -= 1

        # This node is already full - we don't need to store its distribution
        del self.required_flavors_for_nodes[node_name_to_be_filled]

    def postprocess_filing(self):
        # process checks after node is full
        for node_name, node_obj in self.nodes.items():
            # first check - find free/full nodes and exclude them
            # from candidates to be filled
            if not node_obj.vms or node_obj.is_full:
                if node_name in self.node_ids_to_be_recalculated:
                    self.node_ids_to_be_recalculated.pop(
                        self.node_ids_to_be_recalculated.index(node_name))
                    if node_name in self.required_flavors_for_nodes:
                        del self.required_flavors_for_nodes[node_name]
                continue
            # second check - find nodes that need more flavors that we have
            if node_name in self.required_flavors_for_nodes:
                for flavor_obj, count in self.required_flavors_for_nodes[
                        node_name].items():
                    if count > flavor_obj.amount(self):
                        if node_name not in self.node_ids_to_be_recalculated:
                            self.node_ids_to_be_recalculated.append(node_name)

    def condense_recursively(self):
        """
            This method finds vms distribution on nodes with highest density
            it runs recursively until we cannot find better solution
        """
        # calculate how much flavors each node need to be full
        self.calc_required_flavors_for_nodes()

        if not self.required_flavors_for_nodes:
            # we cannot improve result - we are done
            return

        # select node to be filled
        if self.improve_accuracy:
            # use algorithm with better accuracy and higher complexity
            # we use this in the end of condensation
            # in this case we are looking for node with maximal density
            node_name_to_be_filled = max(
                self.required_flavors_for_nodes,
                key=lambda a: self.nodes[a].potential_utilization(
                    self.required_flavors_for_nodes[a]))
            node_to_be_filled = self.nodes[node_name_to_be_filled]
        else:
            # use approximate algorithm that runs faster, but solution is not
            # accurate
            # in this case we are looking for node that requires
            # minimum permutations to be filled
            node_name_to_be_filled = min(
                self.required_flavors_for_nodes,
                key=lambda a: sum(
                    self.required_flavors_for_nodes[a].values()))
            node_to_be_filled = self.nodes[node_name_to_be_filled]
            pot_util = node_to_be_filled.potential_utilization(
                self.required_flavors_for_nodes[node_name_to_be_filled])
            # if potentional utilization of node doesn't full the node
            # it means that we are done with approximation part
            # and we need to switch to accurate algorithm
            if all([i < CONF.condense.precision for i in pot_util]):
                # recalculate for all spare nodes
                return self.condense(True)

        # at this moment we have node to be filled and flavors to put on it
        # we need to do actual job at this step

        # for all flavors that needs to be placed to node we have count
        # of vms of this flavor to be placed on the node
        LOG.info("filing node " + node_name_to_be_filled)
        self.fil_node(node_to_be_filled, node_name_to_be_filled)
        self.postprocess_filing()
        return self.condense_recursively()

    def transfer_nodes(self, cloud):
        """
            This method transfers all nodes without vms to cloud
        """
        for key, value in self.nodes.items():
            if not value.vms:
                self.transfer_node(key, cloud)

    def transfer_node(self, node_name, cloud):
        """
            This method transfers node to another cloud
        """
        node_to_be_transfered = self.nodes.pop(node_name)
        node_to_be_transfered.cloud = cloud
        cloud.nodes[node_to_be_transfered.name] = node_to_be_transfered
        self.actions.add_transfer_action(node_name)

    def get_group_to_migrate(self):
        """
            This method returns next large group
        """
        if self.groups:
            return self.groups.pop(0)

    def check_if_group_fits(self, group_obj, cloud_obj):
        """
            This method tries to assign vms from group from source cloud
            to destination cloud
        """
        # try to assign vms on dst cloud
        list_of_nodes = [i for i in cloud_obj.nodes.values() if not i.is_full]

        flavors_dict = {}
        vm_list = group_obj.get_all_vms()
        for vm_obj in vm_list:
            if vm_obj.flavor not in flavors_dict:
                flavors_dict[vm_obj.flavor] = 0
            flavors_dict[vm_obj.flavor] += 1

        result = {}

        for node_obj in list_of_nodes:
            if not flavors_dict:
                break
            fl_required = node_obj.calculate_flavors_required(flavors_dict)
            if all([i < CONF.condense.precision for i in
                    node_obj.potential_utilization(
                        fl_required)]):
                fl_required = node_obj.calculate_flavors_required(
                    flavors_dict, True)
            result[node_obj] = fl_required
            for flavor_obj, count in fl_required.items():
                flavors_dict[flavor_obj] -= count
                if flavors_dict[flavor_obj] == 0:
                    del flavors_dict[flavor_obj]
        return flavors_dict, result

    def migrate_vms(self, cloud):
        return self.migrate_group(cloud)

    def migrate_group(self, cloud, strict=True):
        """This method migrates single group"""
        group_to_migrate = self.get_group_to_migrate()
        if not group_to_migrate:
            return
        # check that group can fit destination cloud
        flavors_left, distribution = self.check_if_group_fits(
            group_to_migrate, cloud)
        if flavors_left:
            if strict:
                msg = "cannot fit flavors %s" % flavors_left
                raise RuntimeError(msg)
            else:
                self.groups.insert(0, group_to_migrate)
                return
        for node_obj, flavors_required in distribution.items():
            for vm_obj in group_to_migrate.get_all_vms():
                flavor_obj = vm_obj.flavor
                if flavor_obj in flavors_required:
                    flavors_required[flavor_obj] -= 1
                    if flavors_required[flavor_obj] == 0:
                        del flavors_required[flavor_obj]
                    self.migrate_vm(vm_obj, node_obj)
        return self.migrate_group(cloud, False)

    def migrate_vm(self, vm_obj, target_node):
        """This method migrates vm from one cloud to another"""
        vm_obj.link_node(target_node)
        self.actions.add_migration_action(vm_obj, target_node)

    def migrate_to(self, cloud):
        """
        This method contains main logic of application - it processes
        migration"""
        while self.nodes and self.groups:
            self.condense()
            self.transfer_nodes(cloud)
            self.migrate_vms(cloud)
            cloud.condense()
            self.actions.dump_actions()
            cloud.actions.dump_actions()

    def __str__(self):
        """
            This method prints table
        """
        table = prettytable.PrettyTable(
            ['Node', 'Number of VMS', 'Ram Utilization', 'Core Utilization'])
        rows = []
        for node_name, node_obj in self.nodes.items():
            util = node_obj.utilization
            rows.append((node_name, len(node_obj.vms), util[0], util[1]))
        rows = sorted(rows, key=lambda a: a[1], reverse=True)
        for row in rows:
            table.add_row(row)
        return ("\n\n\n\n {total} vms total; {free} nodes free;"
                " {full} nodes full\n cloud - {name} \n"
                "{table}\n\n").format(
                    total=str(sum(i[1] for i in rows)),
                    free=str(len(
                        [i for i in self.nodes.values() if not i.vms])),
                    full=str(len(
                        [i for i in self.nodes.values() if i.is_full])),
                    name=self.name,
                    table=str(table))

    @property
    def groups_info(self):
        return "\n".join([str(i) for i in self.groups])
