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

DEFAULT = 0
PATH_ONE = 1
PATH_TWO = 2


class IsOption(action.Action):

    def __init__(self, init, option_name):
        self.option_name = option_name
        super(IsOption, self).__init__(init)

    def run(self, **kwargs):
        self.set_next_path(DEFAULT)  # DEFAULT PATH
        option_value = self.cfg.migrate[self.option_name]
        if option_value:
            self.set_next_path(PATH_ONE)
        else:
            self.set_next_path(PATH_TWO)
        return {}
