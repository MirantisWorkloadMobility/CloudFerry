from Namespace import Namespace
from Task import Task
from SuperTask import SuperTask
__author__ = 'mirrorcoder'


class Scheduler:
    def __init__(self, namespace=None):
        self.namespace = namespace if namespace else Namespace()
        self.tasks = []
        self.tasks_runned = []

    def addTask(self, task):
        self.tasks.insert(0, task)

    def run(self):
        while self.tasks:
            task = self.tasks.pop()
            if isinstance(task, SuperTask):
                [self.addTask(subtask) for subtask in task.split_task(namespace=self.namespace)]
            else:
                task(self.namespace)
            self.tasks_runned.append(task)
