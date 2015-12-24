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

import copy

from cloudferrylib.base.action import action
from cloudferrylib.utils import log
from cloudferrylib.utils import utils

LOG = log.getLogger(__name__)


class DetachVolumesCompute(action.Action):

    def run(self, info, **kwargs):
        info = copy.deepcopy(info)
        compute_resource = self.cloud.resources[utils.COMPUTE_RESOURCE]
        storage_resource = self.cloud.resources[utils.STORAGE_RESOURCE]
        for instance in info[utils.INSTANCES_TYPE].itervalues():
            LOG.debug("Detaching volumes for instance %s [%s]" %
                      (instance['instance']['name'],
                       instance['instance']['id']))
            if not instance['instance'][utils.VOLUMES_TYPE]:
                continue
            for vol in instance['instance'][utils.VOLUMES_TYPE]:
                volume_status = storage_resource.get_status(vol['id'])
                LOG.debug("Volume %s was found. Status %s" %
                          (vol['id'], volume_status))
                if volume_status == 'in-use':
                    compute_resource.detach_volume(instance['instance']['id'],
                                                   vol['id'])
                    LOG.debug("Detach volume %s" % vol['id'])
                    storage_resource.wait_for_status(
                        vol['id'], storage_resource.get_status, 'available')
        return {}
