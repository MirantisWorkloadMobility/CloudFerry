from scheduler.transaction.TaskTransaction import TransactionsListener
import os
import json
from utils import convert_to_dict
import shutil
from migrationlib.os.utils.snapshot.SnapshotStateOpenStack import SnapshotStateOpenStack

__author__ = 'mirrorcoder'


class TransactionsListenerOs(TransactionsListener):

    def __init__(self, instance=None, rewrite=True, path=None):
        self.instance = instance
        super(TransactionsListenerOs, self).__init__()
        self.transaction = {
            'type': TransactionsListenerOs.__name__,
        }
        if not path:
            self.prefix += TransactionsListenerOs.__name__+"/"
            self.prefix_path = self.prefix+(self.instance.id if self.instance else "")+"/"
            self.transaction['instance'] = self.instance.id
        else:
            self.prefix += path + ("/" if path[-1] != "/" else "")
        if rewrite and os.path.exists(self.prefix):
            shutil.rmtree(self.prefix)

    def event_begin(self, namespace=None):
        self.snapshot_source_begin = SnapshotStateOpenStack(namespace.vars['inst_exporter']).create_snapshot()
        self.snapshot_dest_begin = SnapshotStateOpenStack(namespace.vars['inst_importer']).create_snapshot()
        if not os.path.exists(self.prefix_path):
            os.makedirs(self.prefix_path)
        self.f = open(self.prefix_path+"tasks.trans", "a+")
        with open(self.prefix_path+"snapshot.source.begin", "w+") as f:
            self.__add_obj_to_file(convert_to_dict(self.snapshot_source_begin), f)
        with open(self.prefix_path+"snapshot.dest.begin", "w+") as f:
            self.__add_obj_to_file(convert_to_dict(self.snapshot_dest_begin), f)
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
        self.snapshot_source_end = SnapshotStateOpenStack(namespace.vars['inst_exporter']).create_snapshot()
        self.snapshot_dest_end = SnapshotStateOpenStack(namespace.vars['inst_importer']).create_snapshot()
        with open(self.prefix_path+"snapshot.source.end", "w+") as f:
            self.__add_obj_to_file(convert_to_dict(self.snapshot_source_end), f)
        with open(self.prefix_path+"snapshot.dest.end", "w+") as f:
            self.__add_obj_to_file(convert_to_dict(self.snapshot_dest_end), f)
        diff_snapshot_source = SnapshotStateOpenStack.diff_snapshot(self.snapshot_source_begin,
                                                                    self.snapshot_source_end).convert_to_dict()
        diff_snapshot_dest = SnapshotStateOpenStack.diff_snapshot(self.snapshot_dest_begin,
                                                                  self.snapshot_dest_end).convert_to_dict()
        self.f.close()
        return True

    def __add_obj_to_file(self, obj_dict, file):
        json.dump(obj_dict, file)
        file.write("\n")

    def __prepare_dict(self, dict_namespace, exclude_fields=['config']):
        result = dict_namespace
        for exclude in exclude_fields:
            if exclude in dict_namespace:
                del result[exclude]
        return result

