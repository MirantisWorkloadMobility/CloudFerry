# Copyright (c) 2016 Mirantis Inc.
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

import logging

from cloudferry.lib.base.action import action
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)


class CheckPointVm(action.Action):
    def run(self, info, **kwargs):
        src_compute = self.src_cloud.resources[utils.COMPUTE_RESOURCE]
        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]
        if self.cfg.rollback.keep_migrated_vms:
            for instance_id, instance in info['instances'].items():
                if instance_id in dst_compute.processing_instances:
                    dst_compute.processing_instances.remove(instance_id)
                if instance['old_id'] in src_compute.processing_instances:
                    src_compute.processing_instances.remove(instance['old_id'])
        return {}


class VmRestore(action.Action):
    def run(self, info_backup, **kwargs):
        src_compute = self.src_cloud.resources[utils.COMPUTE_RESOURCE]
        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]
        for instance_id in set(dst_compute.processing_instances +
                               dst_compute.failed_instances):
            LOG.debug("Delete VM %s on DST", instance_id)
            dst_compute.force_delete_vm_by_id(instance_id)
        for instance_id in src_compute.processing_instances:
            instance = info_backup['instances'][instance_id]['instance']
            LOG.debug("Status of '%s' (%s) is changed to original state %s on "
                      "SRC", instance['name'], instance_id, instance['status'])
            # reset status of vm
            src_compute.change_status(
                instance['status'],
                instance_id=instance_id)
        return {}
