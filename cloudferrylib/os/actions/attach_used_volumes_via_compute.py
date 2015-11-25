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

from cinderclient.exceptions import NotFound


LOG = utl.get_log(__name__)


class AttachVolumesCompute(action.Action):

    def run(self, info, **kwargs):
        info = copy.deepcopy(info)
        compute_res = self.cloud.resources[utl.COMPUTE_RESOURCE]
        storage_res = self.cloud.resources[utl.STORAGE_RESOURCE]
        for instance in info[utl.INSTANCES_TYPE].itervalues():
            if not instance[utl.META_INFO].get(utl.VOLUME_BODY):
                continue
            for vol in instance[utl.META_INFO][utl.VOLUME_BODY]:
                try:
                    status = storage_res.get_status(vol['volume']['id'])
                except NotFound:
                    LOG.error("Skipped volume %s: not found and not attached",
                              vol['volume']['id'])
                    continue
                if status == 'available':
                    compute_res.attach_volume_to_instance(instance, vol)
                    storage_res.try_wait_for_status(vol['volume']['id'],
                                                    storage_res.get_status,
                                                    'in-use')
        return {}
