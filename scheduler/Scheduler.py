from SuperTask import SuperTask
from Namespace import Namespace

__author__ = 'mirrorcoder'


class Scheduler:
    def __init__(self, namespace=None):
        self.namespace = namespace if namespace else Namespace()
        self.tasks = []
        self.tasks_runned = []

    def addTask(self, task):
        self.tasks.insert(0, task)

    def push(self, task):
        self.tasks.append(task)

    def run(self):
        while self.tasks:
            task = self.tasks.pop()
            if isinstance(task, SuperTask):
                list_subtasks = [subtask for subtask in task.split_task(namespace=self.namespace)]
                list_subtasks.reverse()
                [self.push(subtask) for subtask in list_subtasks]
            else:
                task(namespace=self.namespace)
            self.tasks_runned.append(task)
