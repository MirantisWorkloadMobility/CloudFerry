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


class IsEndIter(action.Action):

    def __init__(self, init, iter_info_name='info_iter',
                 resource_name=utl.INSTANCES_TYPE):
        self.iter_info_name = iter_info_name
        self.resource_name = resource_name
        super(IsEndIter, self).__init__(init)

    def run(self, **kwargs):
        info = kwargs[self.iter_info_name]
        objs = info[self.resource_name]
        if objs:
            self.num_element = 1
        else:
            self.num_element = 0
        return {}
