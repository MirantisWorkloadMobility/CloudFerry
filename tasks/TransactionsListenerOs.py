from scheduler.transaction.TaskTransaction import TransactionsListener
import os
import json
from utils import convert_to_dict
import shutil
import time
__author__ = 'mirrorcoder'


class TransactionsListenerOs(TransactionsListener):

    def __init__(self, instance=None, rewrite=True, path=None):
        self.instance = instance
        super(TransactionsListenerOs, self).__init__()
        self.transaction = {
            'type': TransactionsListenerOs.__name__,
        }
        if not path:
            self.prefix += "instances/"
            self.prefix_path = self.prefix+(self.instance.id if self.instance else "")+"/"
            self.transaction['instance'] = self.instance.id
        else:
            self.prefix += path + ("/" if path[-1] != "/" else "")
        self.__init_directory(self.prefix, self.prefix_path, rewrite)

    def event_begin(self, namespace=None):
        self.f = open(self.prefix_path+"tasks.trans", "a+")
        if 'snapshots' in namespace.vars:
            self.__save_snapshots(namespace.vars['snapshots'])
        self.__add_obj_to_file(self.transaction, self.f)
        return False

    def event_task(self, namespace=None, task=None, skip=None):
        task_obj = dict()
        task_obj['event'] = 'event task'
        task_obj['namespace'] = self.__prepare_dict(convert_to_dict(namespace))
        task_obj['task'] = str(task)
        task_obj['skip'] = skip
        self.__add_obj_to_file(task_obj, self.f)
        return True

    def event_error(self, namespace=None, task=None, exception=None):
        task_error_obj = dict()
        task_error_obj['event'] = 'event error'
        task_error_obj['namespace'] = self.__prepare_dict(convert_to_dict(namespace))
        task_error_obj['task'] = str(task)
        task_error_obj['exception'] = exception
        self.__add_obj_to_file(task_error_obj, self.f)
        return False

    def event_end(self, namespace=None):
        if 'snapshots' in namespace.vars:
            self.__save_snapshots(namespace.vars['snapshots'])
        task_end = dict()
        task_end['event'] = 'event end'
        self.__add_obj_to_file(task_end, self.f)
        self.f.close()
        return True

    def __init_directory(self, prefix, prefix_path, rewrite):
        if rewrite and os.path.exists(prefix_path):
            shutil.rmtree(prefix_path)
        if not os.path.exists(self.prefix_path):
            os.makedirs(self.prefix_path)
        if not os.path.exists(prefix_path+"source/"):
            os.makedirs(prefix_path+"source/")
        if not os.path.exists(prefix_path+"dest/"):
            os.makedirs(prefix_path+"dest/")

    def __add_obj_to_file(self, obj_dict, file):
        obj_dict['timestamp'] = time.time()
        json.dump(obj_dict, file)
        file.write("\n")

    def __prepare_dict(self, dict_namespace, exclude_fields=['config', 'snapshots']):
        result = dict_namespace
        for exclude in exclude_fields:
            if exclude in dict_namespace:
                del result[exclude]
        return result

    def __save_snapshots(self, snapshots):
        timestamp_source = snapshots['source'][-1].timestamp
        timestamp_dest = snapshots['dest'][-1].timestamp
        with open((self.prefix_path+"source/%s.snapshot") % timestamp_source, "w+") as f:
            self.__add_obj_to_file(convert_to_dict(snapshots['source'][-1]), f)
        with open((self.prefix_path+"dest/%s.snapshot") % timestamp_dest, "w+") as f:
            self.__add_obj_to_file(convert_to_dict(snapshots['dest'][-1]), f)

