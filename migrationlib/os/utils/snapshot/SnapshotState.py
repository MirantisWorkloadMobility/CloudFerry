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
from Snapshot import *
from migrationlib.os.utils.statecloud.StateCloud import StateCloud
__author__ = 'mirrorcoder'


class SnapshotState(StateCloud):
    def create_snapshot(self):
        return Snapshot()

    @staticmethod
    def diff_snapshot(snapshot_one, snapshot_two):
        snapshot_one_res = snapshot_one.convert_to_dict()
        snapshot_two_res = snapshot_two.convert_to_dict()
        snapshot_diff = Snapshot()
        for item_two in snapshot_two_res:
            for obj in snapshot_two_res[item_two]:
                if not obj in snapshot_one_res[item_two]:
                    snapshot_diff.add(obj, item_two, DiffObject(ADD, snapshot_two_res[item_two][obj]))
                elif snapshot_two_res[item_two][obj] != snapshot_one_res[item_two][obj]:
                    snapshot_diff.add(obj, item_two, DiffObject(CHANGE,
                                                                DiffValue(snapshot_one_res[item_two][obj],
                                                                          snapshot_two_res[item_two][obj])))
            for obj in snapshot_one_res[item_two]:
                if not obj in snapshot_two_res[item_two]:
                    snapshot_diff.add(obj, item_two, DiffObject(DELETE, snapshot_one_res[item_two][obj]))
        return snapshot_diff
