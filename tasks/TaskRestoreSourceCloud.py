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

from scheduler.Task import Task
from migrationlib.os.utils.restore.RestoreStateOpenStack import RestoreStateOpenStack
from migrationlib.os.utils.snapshot.SnapshotStateOpenStack import SnapshotStateOpenStack
from migrationlib.os.utils.restore.NoReport import NoReport
from utils import load_json_from_file
from migrationlib.os.utils.snapshot.Snapshot import Snapshot
__author__ = 'mirrorcoder'


class TaskRestoreSourceCloud(Task):

    def __init__(self, namespace=None):
        super(TaskRestoreSourceCloud, self).__init__(namespace=namespace)

    def run(self, inst_exporter=None, snapshots={'source': [], 'dest': []}, **kwargs):
        report = NoReport()
        if len(snapshots['source']) > 1:
            snapshot_one = Snapshot(load_json_from_file(snapshots['source'][-2]['path']))
            snapshot_two = Snapshot(load_json_from_file(snapshots['source'][-1]['path']))
            report = RestoreStateOpenStack(inst_exporter).restore(SnapshotStateOpenStack.diff_snapshot(snapshot_one,
                                                                                                       snapshot_two))
        return {
            'last_report_source': report
        }
