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

CEPH = 'ceph'
ISCSI = 'iscsi'
PATH_TRANSPORT_IMAGE = 0
DEFAULT = 1
INST = utl.INSTANCES_TYPE
BODY = utl.INSTANCE_BODY


class IsNotTransportImage(action.Action):
    def run(self, info=None, **kwargs):
        self.set_next_path(DEFAULT)
        info = copy.deepcopy(info)
        src_compute = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        backend_ephem_drv_src = src_compute.config.compute.backend
        instance_boot = \
            info[INST].values()[0][BODY]['boot_mode']
        if ((instance_boot == utl.BOOT_FROM_IMAGE) and
                (backend_ephem_drv_src == CEPH)):
            self.set_next_path(PATH_TRANSPORT_IMAGE)
        return {
        }
