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

from scheduler.Task import Task
from tests import test
from oslotest import mockpatch


class TaskTestCase(test.TestCase):
    def setUp(self):
        super(TaskTestCase, self).setUp()

    def test_dual_link(self):
        a1 = Task()
        a2 = Task()
        res = a1 >> a2
        self.assertEqual(len(a1.next_element), 1, 'No correct elements in \' a1.next_element\'')
        self.assertIn(a2, a1.next_element)
        self.assertEqual(a2.prev_element, a1)
        self.assertFalse(a1.prev_element)
        self.assertFalse(a2.next_element)

    def test_another_link(self):
        a1 = Task()
        a2 = Task()
        a3 = Task()
        a4 = Task()
        res = (a1 | (a2 - a4) | (a3 - a4)) >> a4
        self.assertEqual(len(a1.next_element), 3, 'No correct elements in \' a1.next_element\'')
        self.assertEqual(a1.next_element[0], a4)
        self.assertEqual(a1.next_element[1], a2)
        self.assertEqual(a1.next_element[2], a3)
        self.assertEqual(a2.next_element[0], a4)
        self.assertEqual(a3.next_element[0], a4)
        self.assertEqual(a4.prev_element, a1)

    def test_closure_link(self):
        a1 = Task()
        a2 = Task()
        res = a1 - a2
        self.assertEqual(len(a1.next_element), 1, 'No correct elements in \' a1.next_element\'')
        self.assertEqual(a1.next_element[0], a2)
        self.assertFalse(a2.prev_element)

    def test_thread_link(self):
        a1 = Task()
        a2 = Task()
        a3 = Task()
        a4 = Task()
        res = (a1 & a2 & a3) >> a4
        self.assertEqual(len(a1.next_element), 1, 'No correct elements in \' a1.next_element\'')
        self.assertEqual(a1.next_element[0], a4)
        self.assertEqual(a4.prev_element, a1)
        self.assertEqual(a1.parall_elem[0], a2)
        self.assertEqual(a1.parall_elem[1], a3)

