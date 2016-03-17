# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import collections
import sys


def sorted_field_names(obj):
    """
    Returns alphabetically sorted list of public object field names (i.e. their
    names don't start with '_')
    """

    return sorted(
        f for f in dir(obj)
        if not f.startswith('_') and not hasattr(getattr(obj, f), '__call__'))


def compute_hash(obj):
    """
    Hash function that is able to compute hashes for lists and dictionaries.
    """

    if isinstance(obj, dict):
        return hash_iterable(sorted(obj.items()))
    elif hasattr(obj, '__iter__'):
        return hash_iterable(obj)
    else:
        return hash(obj)


def hash_iterable(iterable):
    """
    Compute hash for some iterable value
    """
    value = hash(iterable.__class__)
    for item in iterable:
        value = ((value * 1000003) & sys.maxint) ^ compute_hash(item)
    return value


class Hashable(object):
    """
    Mixin class that make objects hashable based on their public fields (i.e.
    which name don't start with '_')
    """

    def __eq__(self, other):
        if other.__class__ != self.__class__:
            return False
        for field in sorted_field_names(self):
            if getattr(self, field) != getattr(other, field, None):
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return compute_hash(getattr(self, f) for f in sorted_field_names(self))


class Representable(object):
    """
    Mixin class that implement __repr__ method that will show all field values
    that are not None.
    """

    def __repr__(self):
        cls = self.__class__
        return '<{module}.{cls} {fields}>'.format(
            module=cls.__module__,
            cls=cls.__name__,
            fields=' '.join('{0}:{1}'.format(f, repr(getattr(self, f)))
                            for f in sorted_field_names(self)
                            if getattr(self, f) is not None))


class ConstructableFromDict(object):
    """
    Mixin class with __init__ method that just assign values from dictionary
    to object attributes with names identical to keys from dictionary.
    """

    def __init__(self, data):
        assert isinstance(data, collections.Mapping)
        for name, value in data.items():
            setattr(self, name, value)
