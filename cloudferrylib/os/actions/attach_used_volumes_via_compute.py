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


class AttachVolumesCompute(action.Action):

    def run(self, info, **kwargs):
        info = copy.deepcopy(info)
        # import pdb; pdb.set_trace()
        compute_resource = self.cloud.resources[utl.COMPUTE_RESOURCE]
        storage_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        for instance in info[utl.COMPUTE_RESOURCE][
                utl.INSTANCES_TYPE].itervalues():
            if not instance[utl.META_INFO].get(utl.VOLUME_BODY):
                continue
            for vol in instance[utl.META_INFO][utl.VOLUME_BODY]:
                if storage_resource.get_status(
                        vol['volume']['id']) != 'in-use':
                    compute_resource.attach_volume_to_instance(instance, vol)
                    storage_resource.wait_for_status(vol['volume']['id'],
                                                     'in-use')
        return {}
