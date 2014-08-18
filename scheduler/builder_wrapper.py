# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.


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

    def __init__(self, func, self_cls, args, kwargs):
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
