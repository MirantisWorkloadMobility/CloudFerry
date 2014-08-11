from Namespace import Namespace

__author__ = 'mirrorcoder'


class Task(object):
    def __init__(self, namespace=Namespace()):
        self.namespace = namespace

    def __call__(self, namespace=None):
        namespace = self.namespace if not namespace else namespace
        result = self.run(**namespace.vars)
        namespace.vars.update(result)
