from Namespace import Namespace
import copy

__author__ = 'mirrorcoder'


def inspect_func(func):
    def wrapper(self, *args, **kwargs):
        if func.__name__ == supertask.__name__:
            return func(self, *args, **kwargs)
        else:
            self.funcs.append(Function(func, self, args, kwargs))
        return self
    return wrapper


def supertask(func):
    def supertask(*args, **kwagrs):
        return func(*args, **kwagrs)
    return supertask


class Function(object):

    def __init__(self, func=None, self_cls=None, args=None, kwargs=None):
        self.f = func
        self.self_cls = self_cls
        self.args = args if args else list()
        self.kwargs = kwargs if kwargs else dict()

    def __call__(self, namespace=None, *args, **kwargs):
        if isinstance(namespace, Namespace):
            for item in namespace.vars:
                if item not in kwargs:
                    kwargs[item] = namespace.vars[item]
        kwargs_copy = copy.copy(self.kwargs)
        kwargs_copy.update(kwargs)
        args = args if args else self.args
        return self.f(self.self_cls, *args, **kwargs_copy)

    def __repr__(self):
        repr = super(Function, self).__repr__()
        return "<Name function: %s - - - %s" % (self.f.__name__, repr)

    def __hash__(self):
        return hash(Function.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)