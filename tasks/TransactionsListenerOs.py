from scheduler.transaction.TaskTransaction import TransactionsListener
import os
import json
import inspect

__author__ = 'mirrorcoder'

primitive = [int, long, bool, float, type(None), str, unicode]

limit_ident = 5


def convert_to_dict(obj, ident = 0):
    ident += 1
    if type(obj) in primitive:
        return obj
    if isinstance(obj, inspect.types.InstanceType) or (type(obj) not in (list, tuple, dict)):
        if 'convert_to_dict' in dir(obj) and (ident <= limit_ident):
            obj = obj.convert_to_dict(ident)
        elif '__dict__' in dir(obj):
            obj = obj.__dict__
            obj['_type_class'] = obj.__class__
        else:
            return obj.__class__
    if type(obj) is dict:
        res = {}
        for item in obj:
            if ident <= limit_ident:
                res[item] = convert_to_dict(obj[item])
            else:
                res[item] = str(obj[item])
        return res
    if type(obj) in (list, tuple):
        res = []
        for item in obj:
            if ident <= limit_ident:
                res.append(convert_to_dict(item))
            else:
                res.append(str(item))
        return res if type(obj) is list else tuple(res)


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
        self.task_obj['task'] = str(task)
        self.task_obj['skip'] = skip
        json.dump(self.task_obj, self.f)
        return True

    def event_error(self, namespace=None, task=None, exception=None):
        self.task_obj['namespace'] = convert_to_dict(namespace)
        self.task_obj['task'] = str(task)
        self.task_obj['exception'] = exception.message()
        json.dump(self.task_obj, self.f)
        return False

    def event_end(self, namespace=None):
        self.f.close()
        return True