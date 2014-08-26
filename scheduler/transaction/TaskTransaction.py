from scheduler.Namespace import Namespace
__author__ = 'mirrorcoder'

NO_ERROR = 0
ERROR = 255


class TransactionsListener(object):
    def __init__(self):
        self.status = NO_ERROR
        self.prefix = "transaction/"


    def event_begin(self, namespace=None):
        return True

    def event_task(self, namespace=None, task=None, skip=None):
        return True

    def event_can_run_next_task(self, namespace=None, task=None, skip=None):
        return True

    def event_error(self, namespace=None, task=None, exception=None):
        return True

    def event_end(self, namespace=None):
        return False

    def __repr__(self):
        return "%s|%s" % (TransactionsListener.__name__, self.__class__.__name__)


class TaskTransactionBegin(object):
    def __init__(self, namespace=Namespace(), transaction_listener=None):
        self.namespace = namespace
        self.transaction_listener = transaction_listener

    def __call__(self, *args, **kwargs):
        return self.transaction_listener

    def __hash__(self):
        return hash(TaskTransactionBegin.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        return "%s|%s" % (TaskTransactionBegin.__name__, self.__class__.__name__)


class TaskTransactionEnd(object):

    def __call__(self, *args, **kwargs):
        pass

    def __hash__(self):
        return hash(TaskTransactionEnd.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        return "%s|%s" % (TaskTransactionEnd.__name__, self.__class__.__name__)
