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
import logging

from cloudferry.lib.base.action import action

LOG = logging.getLogger(__name__)


class StopVms(action.Action):

    def run(self, info, **kwargs):
        info = copy.deepcopy(info)
        compute_resource = self.cloud.resources['compute']
        for instance_id, instance in info['instances'].items():
            LOG.debug("Stop VM '%s' (%s) on %s", instance['instance']['name'],
                      instance_id, self.cloud.position)
            compute_resource.processing_instances.append(instance_id)
            compute_resource.change_status('shutoff', instance_id=instance_id)
        return {}
