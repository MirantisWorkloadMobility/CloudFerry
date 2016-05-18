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

import logging
import multiprocessing

from cloudferry.lib.scheduler import namespace as scheduler_namespace
from cloudferry.lib.utils import errorcodes
from cloudferry.lib.utils import log
from cloudferry.lib.scheduler import cursor
from cloudferry.lib.scheduler import signal_handler
from cloudferry.lib.scheduler import task as scheduler_task
from cloudferry.lib.scheduler import thread_tasks

LOG = logging.getLogger(__name__)

STEP_PREPARATION = "PREPARATION"
STEP_MIGRATION = "MIGRATION"
STEP_ROLLBACK = "ROLLBACK"


class BaseScheduler(object):

    def __init__(self, namespace=None, migration=None, preparation=None,
                 rollback=None):
        self.namespace = (namespace
                          if namespace
                          else scheduler_namespace.Namespace())
        self.status_error = errorcodes.NO_ERROR
        self.migration = migration
        self.preparation = preparation
        self.rollback = rollback
        self.map_func_task = dict() if not hasattr(
            self,
            'map_func_task') else self.map_func_task
        self.map_func_task[scheduler_task.BaseTask()] = self.task_run

    def event_start_task(self, task):
        log.CurrentTaskFilter.current_task = task
        LOG.info("Start task '%s'", task)
        return True

    def event_end_task(self, task):
        LOG.info("End task '%s'", task)
        log.CurrentTaskFilter.current_task = None
        return True

    def error_task(self, task, e):
        LOG.exception("%s TASK FAILED: %s", task, e)
        return True

    def run_task(self, task):
        if self.event_start_task(task):
            self.map_func_task[task](task)
        self.event_end_task(task)

    def process_chain(self, chain, chain_name):
        if chain:
            LOG.info("Processing CHAIN %s", chain_name)
            for task in chain:
                try:
                    self.run_task(task)
                # pylint: disable=broad-except
                except (Exception, signal_handler.InterruptedException) as e:
                    if chain_name == STEP_PREPARATION:
                        self.status_error = errorcodes.ERROR_INITIAL_CHECK
                    if chain_name == STEP_MIGRATION:
                        self.status_error = errorcodes.ERROR_MIGRATION_FAILED
                    if chain_name == STEP_ROLLBACK:
                        self.status_error = errorcodes.ERROR_DURING_ROLLBACK
                    self.error_task(task, e)
                    LOG.info("Failed processing CHAIN %s", chain_name)
                    break
            else:
                LOG.info("Succesfully finished CHAIN %s", chain_name)

    def start(self):
        # try to prepare for migration
        self.process_chain(self.preparation, STEP_PREPARATION)
        # if we didn't get error during preparation task - process migration
        if self.status_error == errorcodes.NO_ERROR:
            with signal_handler.InterruptHandler():
                self.process_chain(self.migration, STEP_MIGRATION)
                # if we had an error during process migration - rollback
                if self.status_error != errorcodes.NO_ERROR:
                    self.process_chain(self.rollback, STEP_ROLLBACK)

    def task_run(self, task):
        task(namespace=self.namespace)


class SchedulerThread(BaseScheduler):
    def __init__(self, namespace=None, thread_task=None, migration=None,
                 preparation=None, rollback=None, scheduler_parent=None):
        super(SchedulerThread, self).__init__(namespace, migration=migration,
                                              preparation=preparation,
                                              rollback=rollback)
        wrap_thread_task = thread_tasks.WrapThreadTask()
        self.map_func_task[wrap_thread_task] = self.task_run_thread
        self.child_threads = dict()
        self.thread_task = thread_task
        self.scheduler_parent = scheduler_parent

    def event_start_children(self, thread_task):
        self.child_threads[thread_task] = True
        return True

    def event_stop_children(self, thread_task):
        del self.child_threads[thread_task]
        return True

    def trigger_start_scheduler(self):
        if self.scheduler_parent:
            self.scheduler_parent.event_start_children(self.thread_task)

    def trigger_stop_scheduler(self):
        if self.scheduler_parent:
            self.scheduler_parent.event_stop_children(self.thread_task)

    def start(self):
        if not self.thread_task:
            self.start_current_thread()
        else:
            self.start_separate_thread()

    def start_separate_thread(self):
        p = multiprocessing.Process(target=self.start_current_thread)
        children = self.namespace.vars[scheduler_namespace.CHILDREN]
        children[self.thread_task]['process'] = p
        p.start()

    def start_current_thread(self):
        self.trigger_start_scheduler()
        super(SchedulerThread, self).start()
        self.trigger_stop_scheduler()

    def fork(self, thread_task, is_deep_copy=False):
        namespace = self.namespace.fork(is_deep_copy)
        scheduler = self.__class__(
            namespace=namespace,
            thread_task=thread_task,
            preparation=self.preparation,
            migration=cursor.Cursor(thread_task.getNet()),
            rollback=self.rollback,
            scheduler_parent=self)
        self.namespace.vars[namespace.CHILDREN][thread_task] = {
            'namespace': namespace,
            'scheduler': scheduler,
            'process': None
        }
        return scheduler

    def task_run_thread(self, task):
        scheduler_fork = self.fork(task)
        scheduler_fork.start()


class Scheduler(SchedulerThread):
    pass
