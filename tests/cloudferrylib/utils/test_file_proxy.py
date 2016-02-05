# Copyright (c) 2016 Mirantis Inc.
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
import os

from cloudferrylib.utils import file_proxy

from tests import test


class GetFileSizeTestCase(test.TestCase):
    def test_none(self):
        self.assertIsNone(file_proxy.get_file_size('fake_file_obj'))

    def test_size(self):
        file_obj = mock.Mock()
        file_obj.tell.side_effect = (0, 10)
        self.assertEqual(10, file_proxy.get_file_size(file_obj))
        self.assertEqual([mock.call(0, os.SEEK_END), mock.call(0)],
                         file_obj.seek.mock_calls)

    def test_ioerror(self):
        file_obj = mock.Mock()
        file_obj.tell.side_effect = IOError
        self.assertIsNone(file_proxy.get_file_size(file_obj))


class FileProxyTestCase(test.TestCase):
    def setUp(self):
        super(FileProxyTestCase, self).setUp()
        m = mock.patch('cloudferrylib.utils.file_proxy.get_file_size')
        self.get_file_size = m.start()
        self.addCleanup(m.stop)
        m = mock.patch('cloudferrylib.utils.file_proxy.SpeedLimiter')
        self.speed_limiter = m.start()
        self.addCleanup(m.stop)
        m = mock.patch('cloudferrylib.utils.file_proxy.ProgressView')
        self.progress_view = m.start()
        self.addCleanup(m.stop)
        m = mock.patch('cloudferrylib.utils.sizeof_format.parse_size')
        self.parse_size = m.start()
        self.addCleanup(m.stop)

    def test_init(self):
        self.get_file_size.return_value = 'fake_file_size'
        self.cfg.set_override('speed_limit', 'fake_speed_limit', 'migrate')
        file_proxy.FileProxy('fake_file')
        self.parse_size.assert_called_once_with('512K')
        self.speed_limiter.assert_called_once_with('fake_speed_limit')
        self.get_file_size.assert_called_once_with('fake_file')
        self.progress_view.assert_called_once_with(name='<file object>',
                                                   size='fake_file_size')

    def test_getattr(self):
        file_obj = mock.Mock()
        fp = file_proxy.FileProxy(file_obj)
        fp.fake_method()
        file_obj.fake_method.assert_called_once_with()
        with mock.patch.object(fp, 'read') as mock_read:
            fp.read()
            mock_read.assert_called_once_with()
            self.assertIsZero(file_obj.read.call_count)

    def test_read(self):
        file_obj = mock.Mock()
        file_obj.read.return_value = 'fake data'
        fp = file_proxy.FileProxy(file_obj)
        fp.read(12345)
        file_obj.read.assert_called_once_with(12345)
        self.progress_view.return_value.assert_called_once_with(9)
        self.speed_limiter.return_value.assert_called_once_with(9)


class SpeedLimiterTestCase(test.TestCase):
    def setUp(self):
        super(SpeedLimiterTestCase, self).setUp()
        m = mock.patch('cloudferrylib.utils.sizeof_format.parse_size')
        self.parse_size = m.start()
        self.addCleanup(m.stop)
        m = mock.patch('time.time')
        self.time = m.start()
        self.addCleanup(m.stop)
        self.speed_limiter = file_proxy.SpeedLimiter('fake_speed_limit')

    def test_init(self):
        self.parse_size.assert_called_once_with('fake_speed_limit')

    def test_call_with_zero_speed_limit(self):
        self.speed_limiter.speed_limit = 0
        self.speed_limiter('fake_size')
        self.assertIsZero(self.speed_limiter.sent_size)

    def test_call_first_time(self):
        self.time.return_value = 1
        self.speed_limiter.speed_limit = 1
        self.speed_limiter(10)
        self.assertEqual(10, self.speed_limiter.sent_size)
        self.assertEqual(1, self.speed_limiter.prev_time)
        self.time.assert_called_once_with()

    def test_call_twice_no_wait(self):
        self.time.side_effect = (1, 2)
        self.speed_limiter.speed_limit = 20
        self.speed_limiter(20)
        self.speed_limiter(10)
        self.assertEqual(30, self.speed_limiter.sent_size)
        self.assertEqual(2, self.time.call_count)
        self.assertEqual(1, self.speed_limiter.prev_time)

    @mock.patch('time.sleep')
    def test_call_twice_and_wait(self, mock_sleep):
        self.time.side_effect = (1, 2, 3)
        self.speed_limiter.speed_limit = 10
        self.speed_limiter(20)
        self.speed_limiter(10)
        self.assertEqual(10, self.speed_limiter.sent_size)
        self.assertEqual(3, self.time.call_count)
        self.assertEqual(3, self.speed_limiter.prev_time)
        mock_sleep.assert_called_once_with(1)


class ProgressViewTestCase(test.TestCase):
    def setUp(self):
        super(ProgressViewTestCase, self).setUp()
        m = mock.patch('cloudferrylib.utils.sizeof_format.sizeof_fmt')
        self.sizeof_fmt = m.start()
        self.sizeof_fmt.return_value = '1000'
        self.addCleanup(m.stop)
        self.progress_view = file_proxy.ProgressView('fake_name', 1000)

    def test_init(self):
        self.sizeof_fmt.assert_called_once_with(1000)
        self.assertEqual(1000, self.progress_view.size)
        self.assertEqual('1000', self.progress_view.size_hr)
        self.assertEqual(10, self.progress_view.show_size)
        self.assertIn('percentage', self.progress_view.progress_message)

    @mock.patch('cloudferrylib.utils.sizeof_format.parse_size')
    def test_init_no_size(self, mock_parse_size):
        self.sizeof_fmt.reset_mock()
        mock_parse_size.return_value = 123
        pv = file_proxy.ProgressView()
        self.assertIsZero(self.sizeof_fmt.call_count)
        self.assertEqual(None, pv.size)
        self.assertEqual('NAN', pv.size_hr)
        self.assertEqual(123, pv.show_size)
        self.assertNotIn('percentage', pv.progress_message)

    def test_inc_progress(self):
        self.assertIsZero(self.progress_view.progress)
        self.progress_view.inc_progress(10)
        self.assertEqual(10, self.progress_view.progress)

    @mock.patch('cloudferrylib.utils.file_proxy.LOG.info')
    def test_show_progress(self, mock_info):
        self.sizeof_fmt.reset_mock()
        self.sizeof_fmt.return_value = '100'
        self.progress_view.progress = 100
        self.progress_view.show_progress()
        self.sizeof_fmt.assert_called_once_with(100)
        mock_info.assert_called_once_with(self.progress_view.progress_message,
                                          {'progress': '100',
                                           'size': '1000',
                                           'name': 'fake_name',
                                           'percentage': 10})

    @mock.patch('time.time')
    def test_call(self, mock_time):
        self.assertIsZero(self.progress_view.current_show_size)
        self.assertIsNone(self.progress_view.first_run)
        mock_time.side_effect = (1, 2, 7)
        with mock.patch.object(self.progress_view, 'inc_progress') as mock_inc:
            with mock.patch.object(self.progress_view,
                                   'show_progress') as mock_show:
                # first time
                self.progress_view(10)
                self.assertEqual(1, self.progress_view.first_run)
                mock_inc.assert_called_once_with(10)
                self.assertEqual(10, self.progress_view.current_show_size)
                self.assertEqual(2, mock_time.call_count)
                self.assertIsZero(mock_show.call_count)

                # second time
                mock_time.reset_mock()
                mock_inc.reset_mock()
                self.progress_view(10)
                self.assertEqual(1, self.progress_view.first_run)
                mock_inc.assert_called_once_with(10)
                self.assertEqual(1, mock_time.call_count)
                self.assertEqual(1, mock_show.call_count)
                self.assertEqual(0, self.progress_view.current_show_size)
