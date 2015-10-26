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
from cloudferrylib.utils.cache import Memoized, Cached

from tests import test


class MemoizationTestCase(test.TestCase):
    def test_treats_self_as_separate_objects(self):
        class C(object):
            def __init__(self, i):
                self.i = i

            @Memoized
            def get_i(self):
                return self.i

        o1 = C(1)
        o2 = C(2)

        self.assertNotEqual(o1.get_i(), o2.get_i())
        self.assertEqual(o1.get_i(), 1)
        self.assertEqual(o2.get_i(), 2)

    def test_takes_value_from_cache(self):
        class C(object):
            def __init__(self, i):
                self.i = i

            @Memoized
            def get_i(self):
                return self.i

            def set_i(self, i):
                self.i = i

        original = 1
        o = C(original)
        self.assertEqual(o.get_i(), original)
        o.set_i(10)
        self.assertEqual(o.get_i(), original)


class CacheTestCase(test.TestCase):
    def test_resets_cache_when_modifier_called(self):
        @Cached(getter='get_i', modifier='set_i')
        class C(object):
            def __init__(self, i):
                self.i = i

            def get_i(self):
                return self.i

            def set_i(self, i):
                self.i = i

        o = C(1)
        self.assertEqual(o.get_i(), 1)

        o.set_i(100)
        self.assertEqual(o.get_i(), 100)
