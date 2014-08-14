from Task import Task
from SuperTask import SuperTask
from Namespace import Namespace
from transaction.TaskTransaction import *

__author__ = 'mirrorcoder'


class Scheduler:
    def __init__(self, namespace=None):
        self.namespace = namespace if namespace else Namespace()
        self.tasks = []
        self.tasks_runned = []
        self.transactions = []
        self.transactions_listener = []
        self.status_error = NO_ERROR
        self.map_func_task = {
            SuperTask: self.__add_tasks_from_supertask,
            Task: self.__task_run,
            TaskTransactionBegin: self.__task_begin_trans,
            TaskTransactionEnd: self.__task_end_trans
        }

    def addTask(self, task):
        self.tasks.insert(0, task)

    def push(self, task):
        self.tasks.append(task)

    def push_transaction(self, task):
        self.transactions.append(task)

    def pop_transaction(self):
        return self.transactions.pop()

    def push_listener_trans(self, listener):
        self.transactions_listener.append(listener)

    def pop_listener_trans(self):
        return self.transactions_listener.pop()

    def get_last_listener(self):
        return self.transactions_listener[-1]

    def trigger_listener(self, name_event, listener=None, args={}):
        if listener:
            self.trigger(name_event, listener, args)
        else:
            for index in range(len(self.transactions_listener)-1, -1, -1):
                if not self.trigger(name_event, self.transactions_listener[index], args):
                    break

    def trigger(self, name_event, listener, args):
        return {
            'event_begin': listener.event_begin,
            'event_end': listener.event_end,
            'event_task': listener.event_task,
            'event_error': listener.event_error
        }[name_event](**args)

    def run(self):
        while self.tasks:
            task = self.tasks.pop()
            try:
                self.map_func_task[task](task)
                self.trigger_listener('event_task', args={'namespace': self.namespace, 'task': task})
            except Exception as e:
                self.status_error = ERROR
                self.trigger_listener('event_error', args={'namespace': self.namespace, 'task': task, 'exception': e})
            finally:
                self.tasks_runned.append(task)

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
        self.pop_transaction()
        self.trigger_listener('event_end', self.pop_listener_trans(), args={'namespace': self.namespace})
