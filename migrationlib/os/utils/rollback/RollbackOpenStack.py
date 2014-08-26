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
from scheduler.transaction.TaskTransaction import ERROR
import os
import json
__author__ = 'mirrorcoder'


class RollbackOpenStack(Rollback):
    def __init__(self, instance_id, cloud_source, cloud_dest):
        self.instance_id = instance_id
        self.cloud_source = cloud_source
        self.cloud_dest = cloud_dest
        self.is_trace = True
        self.skip_all_tasks = False
        self.is_error_instance = False

    def continue_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        if self.skip_all_tasks:
            return False
        if not self.is_trace:
            return True
        obj = self.check_instance(namespace, __transaction__, self.instance_id)
        if not obj:
            self.is_trace = False
            return True
        if obj['status'] == ERROR:
            self.is_error_instance = True

    def abort_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        if not os.path.exists(__transaction__.prefix+"/status.inf"):
            namespace.vars['__rollback_status'] = RESTART
            return True

    def skip_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        if not os.path.exists(__transaction__.prefix+"/status.inf"):
            namespace.vars['__rollback_status'] = RESTART
            return True

    def check_instance(self, namespace, __transaction__, instance_id):
        if not os.path.exists(__transaction__.prefix+"/status.inf"):
            namespace.vars['__rollback_status'] = RESTART
            return True
        obj = {}
        with open(__transaction__.prefix+'/status.inf', 'r') as f:
            for item in f.readlines():
                if item.find(instance_id) != -1:
                    obj = json.loads(item)
                    break
        return obj


    def restart_status(self, __event_name__=None, __transaction__=None, namespace=None, **kwargs):
        return True

