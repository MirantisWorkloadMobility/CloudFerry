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

import collections

from cloudferrylib.base.action import action
from cloudferrylib.base import exception
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)


class CheckNeededComputeResources(action.Action):
    def run(self, **kwargs):
        info = kwargs['info']
        objs = info[utl.INSTANCES_TYPE]
        cnt_map = collections.defaultdict(int)
        for instance in objs.values():
            cnt_map[instance['instance']['flavor_id']] += 1
        needed_cpu = 0
        needed_ram = 0
        needed_hdd = 0
        src_nova = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        for flavor_id, count in cnt_map.items():
            flavor = src_nova.get_flavor_from_id(flavor_id,
                                                 include_deleted=True)
            needed_cpu += flavor.vcpus * count
            needed_hdd += (flavor.disk + flavor.ephemeral) * count
            if flavor.swap:  # if flavor not specified '' is here
                needed_hdd += float(flavor.swap) * count / 1024
                # flavor in Mb instead of disk
            needed_ram += flavor.ram * count
        dst_nova = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        self.check("VCPUs", "", dst_nova.get_free_vcpus(), needed_cpu)
        self.check("RAM", "Mb", dst_nova.get_free_ram(), needed_ram)
        self.check("HDD", "Gb", dst_nova.get_free_disk(), needed_hdd)

    @staticmethod
    def check(name, units, have, needed):
        if have < needed:
            raise exception.OutOfResources("Destination %s not enough. "
                                           "Have %s %s, needed %s %s." % (
                                               name, have, units, needed,
                                               units))
