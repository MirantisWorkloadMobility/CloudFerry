from scheduler.transaction.TaskTransaction import TransactionsListener
from scheduler.transaction.TaskTransaction import ERROR, NO_ERROR
from migrationlib.os.utils.rollback.Rollback import Rollback
import os
import json
from utils import convert_to_dict
import shutil
import time
import uuid
__author__ = 'mirrorcoder'


class TransactionsListenerOs(TransactionsListener):

    def __init__(self, instance=None, rewrite=True, path=None, rollback=Rollback()):
        self.instance = instance
        super(TransactionsListenerOs, self).__init__()
        self.transaction = {
            'type': TransactionsListenerOs.__name__,
        }
        self.id_transaction = uuid.uuid1() if not instance else self.instance.id
        self.prefix += "instances/"
        if not path:
            self.prefix_path = self.prefix+(self.instance.id if self.instance else "")+"/"
            self.transaction['instance'] = self.instance.id
        else:
            self.prefix_path += path + ("/" if path[-1] != "/" else "")
        self.rewrite = rewrite
        self.error_status = NO_ERROR
        self.rollback = rollback

    def event_begin(self, namespace=None, *args, **kwargs):
        handler = self.handler_begin
        kwargs['namespace'] = namespace
        kwargs['__transaction__'] = self
        kwargs['__event_name__'] = 'event_begin'
        return self.preprocessing_rollback(handler,
                                           namespace.vars['__rollback_status__'],
                                           **kwargs)

    def event_can_run_next_task(self, namespace=None, *args, **kwargs):
        handler = self.handler_can_run_next_task
        kwargs['namespace'] = namespace
        kwargs['__transaction__'] = self
        kwargs['__event_name__'] = 'event_can_run_next_task'
        return self.preprocessing_rollback(handler,
                                           namespace.vars['__rollback_status__'],
                                           **kwargs)

    def event_task(self, namespace=None, *args, **kwargs):
        handler = self.handler_task
        kwargs['namespace'] = namespace
        kwargs['__transaction__'] = self
        kwargs['__event_name__'] = 'event_task'
        return self.preprocessing_rollback(handler,
                                           namespace.vars['__rollback_status__'],
                                           **kwargs)

    def event_error(self, namespace=None, *args, **kwargs):
        handler = self.handler_error
        kwargs['namespace'] = namespace
        kwargs['__transaction__'] = self
        kwargs['__event_name__'] = 'event_error'
        return self.preprocessing_rollback(handler,
                                           namespace.vars['__rollback_status__'],
                                           **kwargs)

    def event_end(self, namespace=None, *args, **kwargs):
        handler = self.handler_end
        kwargs['namespace'] = namespace
        kwargs['__transaction__'] = self
        kwargs['__event_name__'] = 'event_end'
        return self.preprocessing_rollback(handler,
                                           namespace.vars['__rollback_status__'],
                                           **kwargs)

    def preprocessing_rollback(self, handler, __rollback_status__, **kwargs):
        return handler(**kwargs) if self.rollback(__rollback_status__,
                                                  **kwargs) else False

    def handler_begin(self, namespace=None, **kwargs):
        self.__init_directory(self.prefix, self.prefix_path, self.rewrite)
        self.f = open(self.prefix_path+"tasks.trans", "a+")
        if 'snapshots' in namespace.vars:
            self.__save_snapshots(namespace.vars['snapshots'])
        self.__add_obj_to_file(self.transaction, self.f)
        return False

    def handler_can_run_next_task(self, namespace=None, task=None, skip=None, **kwargs):
        return True

    def handler_task(self, namespace=None, task=None, skip=None, **kwargs):
        task_obj = dict()
        task_obj['event'] = 'event task'
        task_obj['namespace'] = self.__prepare_dict(convert_to_dict(namespace))
        task_obj['task'] = str(task)
        task_obj['skip'] = skip
        self.__add_obj_to_file(task_obj, self.f)
        return True

    def handler_error(self, namespace=None, task=None, exception=None, **kwargs):
        task_error_obj = dict()
        task_error_obj['event'] = 'event error'
        task_error_obj['namespace'] = self.__prepare_dict(convert_to_dict(namespace))
        task_error_obj['task'] = str(task)
        task_error_obj['exception'] = str(exception)
        self.__add_obj_to_file(task_error_obj, self.f)
        self.error_status = ERROR
        return False

    def handler_end(self, namespace=None, **kwargs):
        if 'snapshots' in namespace.vars:
            self.__save_snapshots(namespace.vars['snapshots'])
        task_end = dict()
        task_end['event'] = 'event end'
        self.__add_obj_to_file(task_end, self.f)
        self.f.close()
        print "event end ", self.id_transaction, self.error_status
        self.__commit_status(self.id_transaction, self.error_status)
        if self.error_status == NO_ERROR:
            return True
        return False

    def __commit_status(self, id_transaction, status):
        commit = {'id_transaction': id_transaction, 'status': status}
        with open(self.prefix+"/status.inf", "a+") as f:
            self.__add_obj_to_file(commit, f)

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
        file.flush()
        os.fsync(file)

    def __prepare_dict(self, dict_namespace, exclude_fields=['config']):
        result = dict_namespace
        for exclude in exclude_fields:
            if exclude in dict_namespace:
                del result[exclude]
        return result

    def __save_snapshots(self, snapshots):
        source = snapshots['source'][-1]
        dest = snapshots['dest'][-1]
        shutil.copy(source['path'], (self.prefix_path+"source/%s.snapshot") % source['timestamp'])
        shutil.copy(dest['path'], (self.prefix_path+"dest/%s.snapshot") % dest['timestamp'])

