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
import sys

from cloudferry.lib.utils import utils


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
        for field in self._get_hashable_fields():
            if getattr(self, field) != getattr(other, field, None):
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return compute_hash(getattr(self, f)
                            for f in sorted(self._get_hashable_fields()))

    def _get_hashable_fields(self):
        return (
            f for f in dir(self)
            if not f.startswith('_') and
            not hasattr(getattr(self, f), '__call__'))


class Representable(object):
    """
    Mixin class that implement __repr__ method that will show all field values
    that are not None.
    """

    def __repr__(self):
        cls = self.__class__
        return '<{module}.{cls} {fields}>'.format(
            module=cls.__module__, cls=cls.__name__,
            fields=' '.join('{0}:{1}'.format(f, repr(getattr(self, f)))
                            for f in sorted(self._get_representable_fields())
                            if getattr(self, f) is not None))

    def _get_representable_fields(self):
        return (
            f for f in dir(self)
            if not f.startswith('_') and
            not hasattr(getattr(self, f), '__call__'))


class ExceptionWithFormatting(Exception):
    """
    Exception to be used as base for exceptions that want to format the
    message.
    E.g. for example::

        class FooException(FormattingException):
            pass

        answer = calculate_answer()
        if answer != 42:
            raise FooException('answer = %d instead of 42', answer)

    will lead to log message like ``FooException: answer = -1 instead of 42``
    """

    def __str__(self):
        try:
            if len(self.args) > 1:
                if isinstance(self.args[0], basestring):
                    # We suspect that anything can happen here, like __repr__
                    # or __str__ raising arbitrary exceptions.
                    # We want to suppress them and deliver to the user as much
                    # original information as we can and don't clutter it with
                    # exception that happend due to conversion of exception to
                    # string.
                    return self.args[0] % self.args[1:]
            elif len(self.args) == 1:
                if isinstance(self.args[0], basestring):
                    return self.args[0]
            else:
                return 'ValidationError'
        except Exception:  # pylint: disable=broad-except
            pass

        # If we got here, then either exception was raised or first argument is
        # not a string
        args_repr = []
        for arg in self.args:
            try:
                args_repr.append(repr(arg))
            except Exception:  # pylint: disable=broad-except
                args_repr.append('<%s id:%d>' % (utils.qualname(type(arg)),
                                                 id(arg)))
        if len(args_repr) == 1:
            return '(' + args_repr[0] + ',)'
        else:
            return '(' + ', '.join(args_repr) + ')'
