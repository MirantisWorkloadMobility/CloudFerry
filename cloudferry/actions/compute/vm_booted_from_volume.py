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


from cloudferry.lib.base.action import action
from cloudferry.lib.utils import utils

BOOT_FROM_IMAGE = 0
BOOT_FROM_VOLUME = 1
INST = utils.INSTANCES_TYPE
BODY = utils.INSTANCE_BODY


class VMBootedFromVolume(action.Action):
    """Sets next action to action passed as argument if VM is booted from
    volume"""

    def run(self, info=None, **kwargs):
        self.set_next_path(BOOT_FROM_VOLUME)
        for instance in info[INST].values():
            instance_boot = instance[BODY]['boot_mode']
            if instance_boot == utils.BOOT_FROM_IMAGE:
                self.set_next_path(BOOT_FROM_IMAGE)
        return {}
