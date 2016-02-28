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


class SnapTransfer(action.Action):
    def __init__(self, init, driver,
                 snap_position):
        super(SnapTransfer, self).__init__(init)
        self.driver = driver(self.src_cloud, self.dst_cloud)
        self.snap_position = snap_position

    def run(self, volume, snapshot_info, **kwargs):
        self.driver.transfer(volume, snapshot_info, self.snap_position)
        return {}
