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
import copy


class Merge(action.Action):

    def __init__(self, init, data1, data2, result, resources_name):
        self.data1 = data1
        self.data2 = data2
        self.result = result
        self.resources_name = resources_name
        super(Merge, self).__init__(init)

    def run(self, **kwargs):
        data1 = copy.deepcopy(kwargs[self.data1])
        data2 = copy.deepcopy(kwargs[self.data2])
        data2[self.resources_name].update(
            data1[self.resources_name]
        )
        return {
            self.result: data2
        }
