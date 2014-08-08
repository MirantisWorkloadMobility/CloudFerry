__author__ = 'mirrorcoder'


class SuperTask:
    def __init__(self, namespace={}):
        self.namespace = namespace

    def run(self):
        pass

    def split_task(self, namespace):
        return self.run(**namespace.vars)