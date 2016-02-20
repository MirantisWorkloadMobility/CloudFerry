# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import functools


class Memoized(object):
    """Decorator. Caches a function's return value each time it is called.
   If called later with the same arguments, the cached value is returned
   (not reevaluated).
   """

    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        key = self._make_key(args, kwargs)
        hashable = True
        try:
            if key in self.cache:
                return self.cache[key]
        except TypeError:
            hashable = False

        # Invoke function and store to cache if key is hashable
        value = self.func(*args, **kwargs)
        if hashable:
            self.cache[key] = value
        return value

    def reset(self):
        self.cache = {}

    @staticmethod
    def _make_key(args, kwargs):
        return args, tuple(sorted(kwargs.items()))

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)


class Cached(object):
    """Property. Modifies class methods at runtime by caching results.

    `getter` - cached method;
    `modifier` - method which modifies cached values. Calling this method
    resets cache.
    """

    def __init__(self, getter, modifier):
        self.getter = getter
        self.modifier = modifier
        self.cacher = None

    def __call__(self, cls):
        getter = getattr(cls, self.getter)
        cached_getter = Memoized(getter)
        setattr(cls, self.getter, cached_getter)

        modifier = getattr(cls, self.modifier)

        def mod(*args, **kwargs):
            cached_getter.reset()
            return modifier(*args, **kwargs)

        setattr(cls, self.modifier, mod)

        return cls
