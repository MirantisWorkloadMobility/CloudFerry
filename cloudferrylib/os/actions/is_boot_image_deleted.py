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


from cloudferrylib.base.action import action

PATH_RECREATE_IMAGE = 0
DEFAULT = 1


class IsBootImageDeleted(action.Action):
    def run(self, info=None, missing_images=None, **kwargs):
        self.set_next_path(DEFAULT)
        if missing_images is not None:
            self.set_next_path(PATH_RECREATE_IMAGE)
