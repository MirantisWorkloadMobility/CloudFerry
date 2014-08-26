from Task import Task
from SuperTask import SuperTask
from Namespace import Namespace
from transaction.TaskTransaction import *
from builder_wrapper import Function
import traceback
__author__ = 'mirrorcoder'


class Scheduler:
    def __init__(self, namespace=None, task_exclusion=[TaskTransactionEnd]):
        self.namespace = namespace if namespace else Namespace()
        self.tasks = []
        self.tasks_runned = []
        self.transactions = []
        self.transactions_listener = []
        self.status_error = NO_ERROR
        self.map_func_task = {
            SuperTask(): self.__add_tasks_from_supertask,
            Task(): self.__task_run,
            Function(): self.__task_run,
            TaskTransactionBegin(): self.__task_begin_trans,
            TaskTransactionEnd(): self.__task_end_trans
        }
        self.task_exclusion = task_exclusion

    def addTask(self, task):
        self.tasks.insert(0, task)

    def addTaskExclusion(self, task_class):
        self.task_exclusion.append(task_class)

    def push(self, task):
        self.tasks.append(task)

    def push_transaction(self, task):
        self.transactions.append(task)

    def has_transactions(self):
        return bool(self.transactions)

    def pop_transaction(self):
        return self.transactions.pop()

    def push_listener_trans(self, listener):
        self.transactions_listener.append(listener)

    def pop_listener_trans(self):
        return self.transactions_listener.pop()

    def get_last_listener(self):
        if len(self.transactions_listener):
            return self.transactions_listener[-1]
        else:
            return None

    def trigger_listener(self, name_event, listener=None, args={}):
        if listener:
            return self.trigger(name_event, listener, args)
        else:
            if self.transactions_listener:
                for index in range(len(self.transactions_listener)-1, -1, -1):
                    if not self.trigger(name_event, self.transactions_listener[index], args):
                        break

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
            if self.has_transactions():
                return self.trigger_listener('event_can_run_next_task',
                                             self.get_last_listener(),
                                             args={'namespace': self.namespace, 'task': task})
            else:
                return True
        elif self.status_error == ERROR:
            return self.__is_task_exclusion(task)

    def __is_task_exclusion(self, task):
        return reduce(lambda result, obj: result or isinstance(task, obj), self.task_exclusion, False)

    def run(self):
        while self.tasks:
            task = self.tasks.pop()
            try:
                skip = True
                if self.__can_run_next_task(task):
                    self.map_func_task[task](task)
                    skip = False
                self.trigger_listener('event_task', args={'namespace': self.namespace, 'task': task, 'skip': skip})
            except Exception as e:
                self.status_error = ERROR
                self.exception = e
                print "Exp msg = ", traceback.print_exc()
                self.trigger_listener('event_error', self.get_last_listener(), args={'namespace': self.namespace,
                                                                                     'task': task,
                                                                                     'exception': e})
            finally:
                self.tasks_runned.append(str(task))

    def __add_tasks_from_supertask(self, task):
        list_subtasks = [subtask for subtask in task.split_task(namespace=self.namespace)]
        list_subtasks.reverse()
        [self.push(subtask) for subtask in list_subtasks]

    def __task_run(self, task):
        task(namespace=self.namespace)

    def __task_begin_trans(self, task):
        self.push_transaction(task)
        self.push_listener_trans(task())
        self.trigger_listener('event_begin', task(), args={'namespace': self.namespace})

    def __task_end_trans(self, task):
        if not self.has_transactions():
            return False
        self.pop_transaction()
        res = self.trigger_listener('event_end', self.pop_listener_trans(), args={'namespace': self.namespace})
        if res:
            self.status_error = NO_ERROR
        else:
            self.status_error = ERROR
            self.trigger_listener('event_error', args={'namespace': self.namespace,
                                                       'task': task,
                                                       'exception': self.exception})

