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

from Task import Task
from Namespace import Namespace
from Task import ThreadTask
import traceback
__author__ = 'mirrorcoder'

NO_ERROR = 0
ERROR = 255


class Scheduler:
    def __init__(self, namespace=None, new_thread=False, netgraph=None, scheduler=None):
        self.namespace = namespace if namespace else Namespace()
        self.tasks = []
        self.status_error = NO_ERROR
        self.netgraph = netgraph
        self.fork_scheduler = []
        self.map_func_task = {
            Task: self.__task_run,
            ThreadTask: self.__thread_task,
        }
        self.new_thread = new_thread
        self.scheduler = scheduler

    def addProcess(self, netgraph):
        self.netgraph = netgraph

    def start(self):
        if self.scheduler:
            self.scheduler.start_scheduler(self)

    def stop(self):
        if self.scheduler:
            self.scheduler.stop_scheduler(self)

    def trigger(self, name_event, listener, args):
        return {
            'event_begin': listener.event_begin,
            'event_can_run_next_task': listener.event_can_run_next_task,
            'event_end': listener.event_end,
            'event_task': listener.event_task,
            'event_error': listener.event_error
        }[name_event](**args)

    def __can_run_next_task(self, task):
        if self.status_error == NO_ERROR:
            return True
        elif self.status_error == ERROR:
            return False

    def fork(self, thread_task, is_deep_copy=False):
        namespace = self.namespace.fork(is_deep_copy)
        scheduler = Scheduler(namespace=namespace, new_thread=True, netgraph=thread_task.getNet())
        self.namespace['__forks__'][thread_task] = {
            'namespace': namespace,
            'scheduler': scheduler
        }
        return scheduler

    def run(self):
        for task in self.netgraph:
            try:
                if self.__can_run_next_task(task):
                    self.map_func_task[task.__class__](task)
            except Exception as e:
                self.status_error = ERROR
                self.exception = e
                print "Exp msg = ", traceback.print_exc()

    def __task_run(self, task):
        task(namespace=self.namespace)

    def __thread_task(self, task):
        pass
