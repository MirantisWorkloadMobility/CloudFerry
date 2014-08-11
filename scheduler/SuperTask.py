from Namespace import Namespace

__author__ = 'mirrorcoder'


class SuperTask(object):
    def __init__(self, namespace=Namespace()):
        self.namespace = namespace

    def run(self):
        pass

    def split_task(self, namespace=None):
        namespace = self.namespace if not namespace else namespace
        return self.run(**namespace.vars)