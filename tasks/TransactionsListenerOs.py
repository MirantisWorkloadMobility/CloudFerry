from scheduler.transaction.TaskTransaction import TransactionsListener
import os
import json

__author__ = 'mirrorcoder'

primitive = [int, long, bool, float, type(None), str, unicode]


def convert_to_dict(obj):
    if type(obj) in primitive:
        return obj
    if

    if type(obj) is dict:
        res = {}
        for item in obj:
            res[item] = convert_to_dict(obj[item])
        return res
    if type(obj) is list or type(obj) is tuple:
        res = ()
        for item in obj:
            res = res + convert_to_dict(item)
        return res


class TransactionsListenerOs(TransactionsListener):

    def __init__(self, instance=None):
        self.instance = instance
        super(TransactionsListenerOs, self).__init__()
        self.prefix_path =\
            self.prefix+TransactionsListenerOs.__name__+"/"+(self.instance.id if self.instance else "")+"/"
        self.transaction = {
            'type': TransactionsListenerOs.__name__,
            'instance': self.instance.id
        }
        self.task_obj = {
            'event': 'task event',
            'namespace': {},
            'task': None,
            'skip': False
        }
        self.task_error_obj = {
            'event': 'task error',
            'namespace': {},
            'task': None,
            'exception': '',
            'traceback': None
        }

    def event_begin(self, namespace=None):
        if not os.path.exists(self.prefix_path):
            os.makedirs(self.prefix_path)
        self.f = open(self.prefix_path+"tasks.trans", "a+")
        json.dump(self.transaction, self.f)
        return False

    def event_task(self, namespace=None, task=None, skip=None):
        self.task_obj['namespace'] = convert_to_dict(namespace)
        self.task_obj['task'] = task
        self.task_obj['skip'] = skip
        json.dump(self.task_obj, self.f)
        return True

    def event_error(self, namespace=None, task=None, exception=None):
        print "event_error= "
        print "task=", task
        print "exception=", exception
        return False

    def event_end(self, namespace=None):
        self.f.close()
        return True