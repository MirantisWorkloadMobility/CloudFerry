from Namespace import Namespace

__author__ = 'mirrorcoder'


class Task(object):
    def __init__(self, namespace=Namespace()):
        self.namespace = namespace

    def __call__(self, namespace=None):
        namespace = self.namespace if not namespace else namespace
        result = self.run(**namespace.vars)
        namespace.vars.update(result)

    def __hash__(self):
        return hash(Task.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        return "Task|%s" % self.__class__.__name__