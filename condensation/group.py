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


class Group(object):

    @classmethod
    def from_dict(cls, data, vm_dict):
        """
            This classmethod creates tree of groups recursively
        """
        groups_list = []
        for group_name, group_data in data.items():
            group = cls(group_name)
            groups_list.append(group)
            # We assume that our group_data is either "dict" or iterable
            if isinstance(group_data, dict):
                # if group_data is "dict"
                group.add_groups(cls.from_dict(group_data, vm_dict))
            else:
                # if group_data is iterable
                for i in group_data:
                    vm_obj = vm_dict.get(i)
                    if vm_obj:
                        group.add_vms({i: vm_obj})
        return sorted(groups_list, key=lambda a: a.capacity, reverse=True)

    def __init__(self, name="null"):
        self.name = name
        self.children = []
        self.parent = None
        self.vms = {}

    def add_groups(self, groups_list):
        """
            This method adds children to self
        """
        self.children.extend(groups_list)
        for group in groups_list:
            group.parent = self

    def add_vms(self, vms_dict):
        """
            This method adds vms to self
        """
        self.vms.update(vms_dict)

    def get_all_vms(self):
        """
            This method gets vms from all children recursively
        """
        result = self.vms.values()
        for child in self.children:
            result.extend(child.get_all_vms())
        # make list distinct
        return list(set(result))

    @property
    def capacity(self):
        """
            This method calculates number of ram, cores required by
            all vms of this group
        """
        flavors = [vm.flavor for vm in self.get_all_vms()]
        return sum(fl.ram for fl in flavors), sum(fl.core for fl in flavors)

    def parent_count(self, count=0):
        """
            This method helps us to build pretty tree
        """
        if self.parent:
            return self.parent.parent_count(count + 1)
        return count

    def __str__(self):
        """
            Print tree of this group and underlying ones
        """
        lines = []
        status_line = ("GROUP -> %s" % self.name)
        status_line += ("\tRAM -> %d\t CORE -> %f" % self.capacity)
        lines.append(status_line)
        if self.vms:
            lines.append("GROUP_VMS:")
            lines.extend([" -" + vm for vm in self.vms.keys()])
        prefix = "\t" * self.parent_count()
        info = "\n".join([prefix + line for line in lines])
        children_info = "\n".join([str(i) for i in self.children])
        if children_info:
            return info + "\n" + children_info
        else:
            return info
