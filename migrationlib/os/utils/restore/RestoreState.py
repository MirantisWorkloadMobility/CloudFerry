
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
from migrationlib.os.utils.statecloud.StateCloud import StateCloud
from migrationlib.os.utils.snapshot.Snapshot import *
from Report import Report
import time
__author__ = 'mirrorcoder'


class RestoreState(StateCloud):

    def restore(self, diff_snapshot):
        return Report()

    def fix(self, id_obj, obj):
        return {
            ADD: self.fix_add,
            DELETE: self.fix_delete,
            CHANGE: self.fix_change
        }[obj.getStatus()](id_obj, obj)

    def fix_add(self, id_obj, obj):
        raise NotImplemented()

    def fix_delete(self, id_obj, obj):
        raise NotImplemented()

    def fix_change(self, id_obj, obj):
        raise NotImplemented()

    def __wait_for_status(self, getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)