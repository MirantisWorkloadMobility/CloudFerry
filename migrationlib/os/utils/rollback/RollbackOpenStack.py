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
from scheduler.transaction.TaskTransaction import NO_ERROR
import os
import json
import shutil
from utils import convert_to_obj
from migrationlib.os.utils.restore_object.RestoreObject import RestoreObject
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

    def continue_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        if self.skip_all_tasks:
            return False
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
            return True
        if __event_name__ == 'event_can_run_next_task':
            state = self.get_state_task(__transaction__)
            if state['event'] == 'event_error':
                self.restore_namespace(namespace, self.instance_id)
                namespace.vars['__rollback_status__'] = RESTART
                self.delete_record_from_status_file(__transaction__, self.instance_id)
            if state['event'] == 'event_task':
                self.make_record_in_file(__transaction__, self.obj)
                return False
            return True
        if __event_name__ == 'event_task':
            return False
        if __event_name__ == 'event_error':
            return True
        if __event_name__ == 'event_end':
            return True

    def abort_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        if self.skip_all_tasks:
            return False
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
            return False
        if __event_name__ == 'event_end':
            return True
        return False

    def skip_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        if self.skip_all_tasks:
            return False
        if not self.is_trace:
            return True
        if not self.obj:
            self.obj = self.check_instance(namespace, __transaction__, self.instance_id)
        if not self.obj:
            self.is_trace = False
            return True
        self.skip_all_tasks = True
        return False

    def cp_info_transaction(self, __transaction__, path_to_instance):
        if os.path.exists(path_to_instance):
            shutil.rmtree(path_to_instance)
        path_to_file_trans = __transaction__.prefix_path
        shutil.copy(path_to_file_trans, path_to_instance)

    def get_state_task(self, task):
        obj = self.find_obj_to_file("%s/%s" % (self.path_to_instance, "tasks.trans"), str(task))
        return obj

    def restore_namespace(self, namespace, state, exclude=('config',)):
        namespace_dict = state['namespace']['vars']
        for item in namespace_dict:
            if item in exclude:
                continue
            obj = convert_to_obj(namespace_dict[item], RestoreObject())
            if item in namespace.vars:
                if hasattr(namespace.vars[item], 'set_state'):
                    namespace.vars[item].set_state(obj)
                    continue
            namespace.vars[item] = obj

    def make_record_in_file(self, __transaction__, state):
        f = __transaction__.f
        json.dump(state, f)
        f.write("\n")
        f.flush()

    def delete_record_from_status_file(self, __transaction__, obj):
        path_to_status = __transaction__.prefix+'status.inf'
        s = json.dumps(obj)+"\n"
        with open(path_to_status, 'w+') as f:
            f.write(f.read().replace(s, ""))

    def check_instance(self, namespace, __transaction__, instance_id):
        obj = {}
        if self.check_status_file(__transaction__, namespace):
            obj = self.find_obj_to_file(__transaction__.prefix+'/status.inf', instance_id)
        return obj

    def check_status_file(self, __transaction__, namespace):
        if not os.path.exists(__transaction__.prefix+"/status.inf"):
            namespace.vars['__rollback_status__'] = RESTART
            return False
        return True

    def find_obj_to_file(self, path, instance_id):
        obj = {}
        with open(path, 'r') as f:
            for item in f.readlines():
                if item.find(instance_id) != -1:
                    obj = json.loads(item)
                    break
        return obj

    def restart_status(self, *args, **kwargs):
        return True

