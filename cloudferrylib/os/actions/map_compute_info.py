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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl
import copy

INSTANCES = 'instances'
DIFF = 'diff'

PATH_DST = 'path_dst'
HOST_DST = 'host_dst'


class MapComputeInfo(action.Action):

    def run(self, info=None, **kwargs):

        new_info = copy.deepcopy(info)

        for instance_id, instance in new_info[utl.INSTANCES_TYPE].iteritems():
            # TODO: path_dst is probably non used code, need functional testing
            self.dst_cloud.cloud_config.cloud.temp = '-'
            path_dst = "%s/%s" % (self.dst_cloud.cloud_config.cloud.temp,
                                  "temp%s_base" % instance_id)
            instance[DIFF][PATH_DST] = path_dst
            instance[DIFF][HOST_DST] = \
                self.dst_cloud.cloud_config.cloud.ssh_host
        return {
            'info': new_info
        }
