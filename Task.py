__author__ = 'mirrorcoder'


class Task:
    def __init__(self, namespace={}):
        self.namespace = namespace

    def __call__(self, namespace):
        result = self.func(**namespace.vars)
        namespace.vars.update(result)