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
from migrationlib.os.utils.snapshot.SnapshotStateOpenStack import SnapshotStateOpenStack
from utils import convert_to_dict
import os
import json
__author__ = 'mirrorcoder'


class TaskCreateSnapshotOs(Task):

    def __init__(self, namespace=None):
        self.prefix = "snapshots"
        super(TaskCreateSnapshotOs, self).__init__(namespace=namespace)
        self.__init_directory(self.prefix)

    def run(self, inst_exporter=None, inst_importer=None, snapshots={'source': [], 'dest': []}, **kwargs):
        snapshot_source = SnapshotStateOpenStack(inst_exporter).create_snapshot()
        snapshot_dest = SnapshotStateOpenStack(inst_importer).create_snapshot()
        path_source = "%s/source/%s.snapshot" % (self.prefix, snapshot_source.timestamp)
        path_dest = "%s/dest/%s.snapshot" % (self.prefix, snapshot_dest.timestamp)
        snapshots['source'].append({'path': path_source, 'timestamp': snapshot_source.timestamp})
        snapshots['dest'].append({'path': path_dest, 'timestamp': snapshot_dest.timestamp})
        self.__dump_to_file(path_source, snapshot_source)
        self.__dump_to_file(path_dest, snapshot_dest)
        return {
            'snapshots': snapshots
        }

    def __init_directory(self, prefix):
        if not os.path.exists("%s/source" % prefix):
            os.makedirs("%s/source" % prefix)
        if not os.path.exists("%s/dest" % prefix):
            os.makedirs("%s/dest" % prefix)

    def __dump_to_file(self, path, snapshot):
        with open(path, "w+") as f:
            json.dump(convert_to_dict(snapshot), f)

