from Namespace import Namespace

__author__ = 'mirrorcoder'


class SuperTask(object):
    def __init__(self, namespace=Namespace()):
        self.namespace = namespace

    def run(self):
        pass

    def split_task(self, namespace=None):
        namespace = self.namespace if not namespace else namespace
        self.namespace = namespace
        tasks = self.run(**namespace.vars)
        return tasks

    def __hash__(self):
        return hash(SuperTask.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        return "SuperTask|%s" % self.__class__.__name__