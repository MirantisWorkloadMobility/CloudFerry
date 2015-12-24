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
from cloudferrylib.utils import log
from cloudferrylib.utils import utils

LOG = log.getLogger(__name__)


class RemoveFailedInstances(action.Action):
    """ Remove the wrong copies of deployed instances. """
    def run(self, **kwargs):
        dst_compute = self.cloud.resources[utils.COMPUTE_RESOURCE]
        for vm_id in dst_compute.failed_instances:
            dst_compute.force_delete_vm_by_id(vm_id)
        failed_instances = dst_compute.failed_instances
        if failed_instances:
            LOG.warning('During deployment some instances were failed and '
                        'redeployed with keeping wrong copies which should be '
                        'deleted; the ids: %s', failed_instances)
