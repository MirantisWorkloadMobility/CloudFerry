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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)
VM_STATUSES = "VM_STATUSES"


class VmSnapshotBasic(action.Action):

    """Base class that contains common to vm_snapshot methods"""

    def get_compute_resource(self):
        """returns cloudferry compute resource"""
        return self.cloud.resources[utils.COMPUTE_RESOURCE]

    @property
    def namespace_variable(self):
        """returns unique for cloud variable from namespace"""
        return '_'.join([VM_STATUSES, self.cloud.position])

    def get_list_of_vms(self):
        search_opts = {'all_tenants': 'True'}
        return self.get_compute_resource().get_instances_list(
            search_opts=search_opts)


class VmSnapshot(VmSnapshotBasic):

    def run(self, *args, **kwargs):
        LOG.debug("creation of vm snapshots")
        # we gonna store only id and vm status in the state (for now)
        state_to_record = {}
        for vm in self.get_list_of_vms():
            state_to_record.update({vm.id: vm.status})
        return {self.namespace_variable: state_to_record}


class VmRestore(VmSnapshotBasic):

    def run(self, *args, **kwargs):
        LOG.debug("restoring vms from snapshot")
        snapshot_from_namespace = kwargs.get(self.namespace_variable)
        compute = self.get_compute_resource()
        for vm in self.get_list_of_vms():
            if vm.id not in snapshot_from_namespace:
                # delete this vm - we don't have its id in snapshot data
                LOG.debug("vm {vm} will be deleted on {location}".format(
                    vm=vm.id,
                    location=self.cloud.position))
                compute.delete_vm_by_id(vm.id)
            elif vm.status != snapshot_from_namespace.get(vm.id):
                LOG.debug("status of {vm} is changed from {original}"
                          " to {new} on {location}".format(
                              vm=vm.id,
                              original=vm.status,
                              new=snapshot_from_namespace.get(vm.id),
                              location=self.cloud.position))
                # reset status of vm
                compute.change_status(
                    snapshot_from_namespace.get(vm.id),
                    instance_id=vm.id)
        return {}
