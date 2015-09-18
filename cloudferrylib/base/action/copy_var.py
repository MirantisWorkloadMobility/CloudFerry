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


class CopyVar(action.Action):

    def __init__(self, init, original_info_name, info_name, deepcopy=False):
        self.original_info_name = original_info_name
        self.info_name = info_name
        self.deepcopy = deepcopy
        super(CopyVar, self).__init__(init)

    def run(self, **kwargs):
        if not self.deepcopy:
            new_obj = copy.copy(kwargs[self.original_info_name])
        else:
            new_obj = copy.deepcopy(kwargs[self.original_info_name])
        return {
            self.info_name: new_obj
        }
