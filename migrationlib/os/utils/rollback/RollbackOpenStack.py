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
from Rollback import *
from migrationlib.os.utils.snapshot.Snapshot import Snapshot
from scheduler.transaction.TaskTransaction import NO_ERROR, ERROR
import os
import json
import shutil
from migrationlib.os.utils.restore.RestoreStateOpenStack import RestoreStateOpenStack
from migrationlib.os.utils.snapshot.SnapshotStateOpenStack import SnapshotStateOpenStack
from scheduler.transaction.TaskTransaction import TaskTransactionEnd
from utils import load_json_from_file, dump_to_file
__author__ = 'mirrorcoder'

PATH_TO_ROLLBACK = 'transaction/rollback'


class RollbackOpenStack(Rollback):
    def __init__(self, instance_id, cloud_source, cloud_dest):
        self.instance_id = instance_id
        self.cloud_source = cloud_source
        self.cloud_dest = cloud_dest
        self.is_trace = True
        self.skip_all_tasks = False
        self.is_error_instance = False
        self.obj = None
        self.path_to_instance = "%s/%s" % (PATH_TO_ROLLBACK, instance_id)

    def retry_status(self, __event_name__=None, __transaction__=None, namespace=None, task=None, **kwargs):
        if self.skip_all_tasks:
            return self.is_exclude(task)
        if not self.is_trace:
            return True
        if not self.obj:
            self.obj = self.check_instance(namespace, __transaction__, self.instance_id)
        if not self.obj:
            self.is_trace = False
            return True
        if self.obj['status'] == NO_ERROR:
            self.skip_all_tasks = True
            return False
        self.is_error_instance = True
        if __event_name__ == 'event_begin':
            self.cp_info_transaction(__transaction__, self.path_to_instance)
            self.restore_state_openstack(namespace.vars['inst_exporter'],
                                         namespace.vars['inst_importer'],
                                         __transaction__)
            self.add_snapshots_to_namespace(namespace)
            self.delete_record_from_status_file(__transaction__, self.instance_id)
        return True

    def skip_status(self, __event_name__=None, __transaction__=None, namespace=None, task=None, **kwargs):
        if self.skip_all_tasks:
            return self.is_exclude(task)
        if not self.is_trace:
            return True
        if not self.obj:
            self.obj = self.check_instance(namespace, __transaction__, self.instance_id)
        if not self.obj:
            self.is_trace = False
            return True
        if self.obj['status'] == NO_ERROR:
            self.skip_all_tasks = True
            return False
        self.is_error_instance = True
        if __event_name__ == 'event_begin':
            self.cp_info_transaction(__transaction__, self.path_to_instance)
            self.restore_state_openstack(namespace.vars['inst_exporter'],
                                         namespace.vars['inst_importer'],
                                         __transaction__)
            self.add_snapshots_to_namespace(namespace)
            self.delete_record_from_status_file(__transaction__, self.instance_id)
            self.skip_all_tasks = False
        return False

    def add_snapshots_to_namespace(self, namespace):
        prefix = 'snapshots'
        importer = namespace.vars['inst_importer']
        exporter = namespace.vars['inst_exporter']
        snapshot_source = SnapshotStateOpenStack(exporter).create_snapshot()
        snapshot_dest = SnapshotStateOpenStack(importer).create_snapshot()
        path_source = "%s/source/%s.snapshot" % (prefix, snapshot_source.timestamp)
        path_dest = "%s/dest/%s.snapshot" % (prefix, snapshot_dest.timestamp)
        namespace.vars['snapshots']['source'].append({'path': path_source, 'timestamp': snapshot_source.timestamp})
        namespace.vars['snapshots']['dest'].append({'path': path_dest, 'timestamp': snapshot_dest.timestamp})
        dump_to_file(path_source, snapshot_source)
        dump_to_file(path_dest, snapshot_dest)

    def is_exclude(self, task=None):
        if task:
            if isinstance(task, TaskTransactionEnd):
                return True
        return False

    def get_snapshots(self, __transaction__, cloud, path, is_do_snapshot_two=False):
        path_to_snap = __transaction__.prefix_path+path
        list_snapshots = os.listdir(path_to_snap)
        list_snapshots.sort()
        snapshot_one_s = Snapshot(load_json_from_file(path_to_snap+list_snapshots[0]))
        if is_do_snapshot_two:
            snapshot_two_s = SnapshotStateOpenStack(cloud).create_snapshot()\
                if len(list_snapshots) < 2 else \
                Snapshot(load_json_from_file(path_to_snap+list_snapshots[-1]))
        else:
            snapshot_two_s = SnapshotStateOpenStack(cloud).create_snapshot()
        return snapshot_one_s, snapshot_two_s

    def restore_state_openstack(self, exporter, importer, __transaction__):
        snapshot_one_s, snapshot_two_s = self.get_snapshots(__transaction__,
                                                            exporter,
                                                            path="source/")
        snapshot_one_d, snapshot_two_d = self.get_snapshots(__transaction__,
                                                            importer,
                                                            path="dest/",
                                                            is_do_snapshot_two=True)
        report_s = self.restore_from_snapshot(snapshot_one_s, snapshot_two_s, exporter)
        report_d = self.restore_from_snapshot(snapshot_one_d, snapshot_two_d, importer)
        return report_s, report_d

    def restore_from_snapshot(self, snapshot_one, snapshot_two, inst_exporter):
        return RestoreStateOpenStack(inst_exporter).restore(SnapshotStateOpenStack.diff_snapshot(snapshot_one,
                                                                                                 snapshot_two))

    def cp_info_transaction(self, __transaction__, path_to_instance):
        if os.path.exists(path_to_instance):
            shutil.rmtree(path_to_instance)
        path_to_file_trans = __transaction__.prefix_path
        shutil.copytree(path_to_file_trans, path_to_instance)

    def delete_record_from_status_file(self, __transaction__, instance_id):
        path_to_status = __transaction__.prefix+'status.inf'
        path_to_status_temp = PATH_TO_ROLLBACK+'/status.inf.temp'
        with open(path_to_status_temp, 'w+') as t:
            with open(path_to_status, 'r+') as f:
                for item in f.readlines():
                    if item.find(instance_id) == -1:
                        t.write(item)
        os.remove(path_to_status)
        os.renames(path_to_status_temp, path_to_status)

    def check_instance(self, namespace, __transaction__, instance_id):
        obj = {}
        obj_b = {}
        if self.check_status_file(__transaction__, namespace):
            obj_1 = self.find_obj_to_file(__transaction__.prefix+'status.inf', instance_id)
            obj_2 = self.find_obj_to_file(__transaction__.prefix+'status.inf', instance_id, 1)
            for o in [obj_2, obj_1]:
                if o:
                    if o['event'] == 'event_end':
                        obj = o
                    if o['event'] == 'event_begin':
                        obj_b = o
            if not obj:
                if obj_b:
                    obj = obj_b
                    obj['status'] = ERROR
        return obj

    def check_status_file(self, __transaction__, namespace):
        if not os.path.exists(__transaction__.prefix+"/status.inf"):
            namespace.vars['__rollback_status__'] = RESTART
            return False
        return True

    def find_obj_to_file(self, path, instance_id, skip=0):
        obj = {}
        skip_curr = 0
        with open(path, 'r') as f:
            for item in f.readlines():
                if item.find(instance_id) != -1:
                    if skip_curr < skip:
                        skip_curr += 1
                        continue
                    obj = json.loads(item)
                    break
        return obj

    def restart_status(self, *args, **kwargs):
        if self.skip_all_tasks:
            return False
        if not self.is_trace:
            return True
        return True

