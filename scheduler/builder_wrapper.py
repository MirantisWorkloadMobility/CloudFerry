from Namespace import Namespace

__author__ = 'mirrorcoder'


def inspect_func(func):
    def wrapper(self, *args, **kwargs):
        if func.__name__ == supertask.__name__:
            return func(self, *args, **kwargs)
        else:
            self.funcs.append(Function(func, self))
        return self
    return wrapper


def supertask(func):
    def supertask(*args, **kwagrs):
        return func(*args, **kwagrs)
    return supertask


class Function(object):

    def __init__(self, func, self_cls):
        self.f = func
        self.self_cls = self_cls

    def __call__(self, namespace=None, *args, **kwargs):
        if isinstance(namespace, Namespace):
            kwargs.update(namespace.vars)
        return self.f(self.self_cls, *args, **kwargs)

    def __repr__(self):
        repr = super(Function, self).__repr__()
        return "<Name function: %s - - - %s" % (self.f.__name__, repr)
