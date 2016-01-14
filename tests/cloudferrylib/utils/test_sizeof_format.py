# Copyright (c) 2015 Mirantis Inc.
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

from cloudferrylib.utils import sizeof_format
from tests import test


class SizeOfFormatTestCase(test.TestCase):
    def setUp(self):
        super(SizeOfFormatTestCase, self).setUp()
        self.num = 123456789

    def test_default(self):
        res = sizeof_format.sizeof_fmt(self.num)
        self.assertEqual('117.7MB', res)

    def test_current_unit_mega(self):
        res = sizeof_format.sizeof_fmt(self.num, unit='M')
        self.assertEqual('117.7TB', res)

    def test_current_unit_mega_lowercase(self):
        res = sizeof_format.sizeof_fmt(self.num, unit='m')
        self.assertEqual('117.7TB', res)

    def test_fake_current_unit(self):
        self.assertRaises(ValueError, sizeof_format.sizeof_fmt, self.num, 'F')


class ParseSizeTestCase(test.TestCase):
    def parse_size(self, speed_limit=None):
        return sizeof_format.parse_size(speed_limit)

    def test_none(self):
        self.assertIsZero(self.parse_size())

    def test_off(self):
        self.assertIsZero(self.parse_size('off'))
        self.assertIsZero(self.parse_size('OFF'))
        self.assertIsZero(self.parse_size('Off'))

    def test_parse(self):
        for expected_result, value in ((1, '1'), (1, '1b'),
                                       (1024, '1kb'),
                                       (1024 * 1024, '1mb'),
                                       (1024 * 1024 * 1024, '1gb')):
            result = self.parse_size(value)
            self.assertEqual(expected_result, result)

    def test_trash(self):
        self.assertIsZero(self.parse_size('fake_value'))

    def test_int(self):
        self.assertEqual(123456789, self.parse_size(123456789))

    def test_zero(self):
        self.assertIsZero(self.parse_size(0))
        self.assertIsZero(self.parse_size('0'))
