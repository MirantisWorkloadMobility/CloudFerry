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

from condensation import flavor as flavors


class Vm(object):

    """ This class is representation of OpenStack System"""

    def __init__(self, node, vm_id, flavor):
        self.vm_id = vm_id
        self.node = None
        self.flavor = None
        if flavor is None:
            flavor = flavors.default
        self.link_node(node)
        self.link_flavor(flavor)

    def link_node(self, node):
        """
            This method links Vm with given Node
            in case we allready have node - we need to notify about it
        """
        if self.node:
            self.node.unlink_vm(self)
        self.node = node
        self.node.link_vm(self)

    def link_flavor(self, flavor):
        """
            This method links Vm with given Flavor
        """
        self.flavor = flavor
        self.flavor.link_vm(self)
