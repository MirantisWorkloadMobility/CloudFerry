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
import random
import collections

from cloudferry.lib.utils import bases
from tests import test


class Abc(bases.Hashable, bases.Representable):
    def __init__(self, a=1, b=2, c=None):
        self.a = a
        self.b = b
        self.c = c

abc_qualname = bases.utils.qualname(Abc)


class BasesTestCase(test.TestCase):
    def setUp(self):
        super(BasesTestCase, self).setUp()
        self.random_seed = 1155051716

    def _shuffle_dict(self, source):
        rnd = random.Random(self.random_seed)
        result = collections.OrderedDict()
        items = source.items()
        rnd.shuffle(items)
        for key, value in items:
            result[key] = value
        return result

    def test_omnivorous_hash(self):
        src = {
            'foo': 'bar',
            50000: None,
            ('what', 42): 5.0,
            5.1: [41, 42, 43],
        }
        dst = self._shuffle_dict(src)

        self.assertEqual(hash(Abc(c=src)), hash(Abc(c=dst)))
        dst[10] = 10
        self.assertNotEqual(hash(Abc(c=src)), hash(Abc(c=dst)))

    def test_representable(self):
        self.assertEquals(repr(Abc(c=None)),
                          '<{0} a:1 b:2>'.format(abc_qualname))
        self.assertEquals(repr(Abc(c=5)),
                          '<{0} a:1 b:2 c:5>'.format(abc_qualname))


class ExceptionWithFormatTestCase(test.TestCase):
    def test_exception_formatting(self):
        ex = bases.ExceptionWithFormatting('foo %s baz', 'bar')
        self.assertEqual('foo bar baz', str(ex))

    def test_exception_formatting_invalid_formatting1(self):
        ex = bases.ExceptionWithFormatting('foo %s baz')
        self.assertEqual('foo %s baz', str(ex))

    def test_exception_formatting_invalid_formatting2(self):
        ex = bases.ExceptionWithFormatting(123)
        self.assertEqual('(123,)', str(ex))

    def test_exception_formatting_invalid_formatting3(self):
        ex = bases.ExceptionWithFormatting('%d', 123, 456)
        self.assertEqual('(\'%d\', 123, 456)', str(ex))
