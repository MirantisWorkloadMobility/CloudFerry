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

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class DissociateFloatingip(action.Action):

    def run(self, info=None, **kwargs):

        info_compute = copy.deepcopy(info)
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]

        instances = info_compute[utl.COMPUTE_RESOURCE][utl.INSTANCES_TYPE]

        for instance in instances.values():
            networks_info = instance[utl.INSTANCE_BODY][utl.INTERFACES]
            old_id = instance[utl.OLD_ID]
            for net in networks_info:
                if net['floatingip']:
                    compute_resource.dissociate_floatingip(old_id, net['floatingip'])
        return {}







