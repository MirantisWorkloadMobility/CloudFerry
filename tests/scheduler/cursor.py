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


import mock

from cloudferrylib.scheduler import cursor
from tests import test


class CursorTestCase(test.TestCase):
    def setUp(self):
        super(CursorTestCase, self).setUp()
        self.elements = [
            mock.Mock(next_element=[], prev_element=None, parall_elem=[],
                      num_element=cursor.DEFAULT) for i in xrange(7)]
        self.elements[0].next_element = [self.elements[1]]
        self.elements[1].prev_element = self.elements[0]
        self.elements[1].next_element = [self.elements[4], self.elements[2],
                                         self.elements[3]]
        self.elements[2].prev_element = self.elements[1]
        self.elements[3].prev_element = self.elements[1]
        self.elements[2].next_element = [self.elements[4]]
        self.elements[3].next_element = [self.elements[4]]
        self.elements[4].prev_element = self.elements[1]
        self.elements[4].next_element = [self.elements[5]]
        self.elements[4].parall_elem = [self.elements[6]]
        self.elements[5].prev_element = self.elements[4]
        # 0 <-> 1 | (2 -> 4,3 -> 4) <-> 4 & (6) <-> 5

    def test_cursor(self):
        cur = cursor.Cursor(self.elements[5])
        self.assertEqual(cur.current(), self.elements[0])

    # def test_iterating_first_case_cursor(self):
    #    cur = cursor.Cursor(self.elements[0])
    #    expected_result = [self.elements[0], self.elements[1],
    #                       self.elements[4], self.elements[6],
    #                       self.elements[5]]
    #    expected_result.reverse()
    #    for c in cur:
    #        self.assertEqual(expected_result.pop(), c)
    #
    # def test_iterating_second_case_cursor(self):
    #    self.elements[1].num_element = 1
    #    cur = cursor.Cursor(self.elements[0])
    #    expected_result = [self.elements[0], self.elements[1],
    #                       self.elements[2], self.elements[4],
    #                       self.elements[6],
    #                       self.elements[5]]
    #    expected_result.reverse()
    #    for c in cur:
    #        self.assertEqual(expected_result.pop(), c)
    #
    # def test_iterating_third_case_cursor(self):
    #    self.elements[1].num_element = 2
    #    cur = cursor.Cursor(self.elements[0])
    #    expected_result = [self.elements[0], self.elements[1],
    #                       self.elements[3], self.elements[4],
    #                       self.elements[6],
    #                       self.elements[5]]
    #    expected_result.reverse()
    #    for c in cur:
    #        self.assertEqual(expected_result.pop(), c)
    #
    # def test_iterating_fourth_case_cursor(self):
    #    self.elements[1].num_element = 3
    #    cur = cursor.Cursor(self.elements[0])
    #    expected_result = [self.elements[0], self.elements[1],
    #                       self.elements[4], self.elements[6],
    #                       self.elements[5]]
    #    expected_result.reverse()
    #    for c in cur:
    #        self.assertEqual(expected_result.pop(), c)
