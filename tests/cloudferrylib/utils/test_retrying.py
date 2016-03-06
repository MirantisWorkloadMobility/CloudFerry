# Copyright 2016 Mirantis Inc.
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

import mock

from tests import test

from cloudferrylib.utils import retrying


@mock.patch('time.sleep')
class RetryTestCase(test.TestCase):
    def test_function_is_called_once_by_default(self, sleep_mock):
        retryer = retrying.retry()

        def func():
            pass

        retryer.run(func)

        self.assertFalse(sleep_mock.called)
        self.assertEqual(retryer.attempt, 1)

    def test_raises_last_error_if_all_attempts_failed(self, sleep_mock):
        retry = retrying.Retry(max_attempts=5, wait_exponential=False,
                               reraise_original_exception=True)

        @retry
        def func():
            raise ValueError()

        self.assertRaises(ValueError, func)
        self.assertEqual(retry.attempt, retry.max_attempts)
        self.assertEqual(sleep_mock.call_count, retry.max_attempts)

    def test_raises_expected_exception(self, sleep_mock):
        retry = retrying.Retry(max_attempts=10, expected_exceptions=[KeyError])

        @retry
        def func():
            raise KeyError()

        self.assertRaises(KeyError, func)
        self.assertEqual(retry.attempt, 1)
        self.assertFalse(sleep_mock.called)

    def test_retries_on_invalid_return_value(self, sleep_mock):
        bad_value = 10

        retry = retrying.Retry(max_attempts=5,
                               retry_on_return_value=True,
                               return_value=bad_value,
                               raise_error=False)

        @retry
        def func():
            return bad_value

        func()

        self.assertEqual(retry.attempt, retry.max_attempts)
        self.assertEqual(sleep_mock.call_count, retry.max_attempts)

    def test_retries_until_timed_out(self, sleep_mock):
        retry = retrying.Retry(max_time=100,
                               wait_exponential=True,
                               raise_error=False)

        @retry
        def func():
            raise RuntimeError()

        func()

        self.assertTrue(retry.total_time >= retry.max_time)
        self.assertTrue(sleep_mock.called)

    def test_retries_if_predicate_fails(self, sleep_mock):
        def always_fail():
            return False

        retry = retrying.Retry(max_attempts=5,
                               wait_exponential=True,
                               raise_error=False,
                               predicate=always_fail)

        @retry
        def func():
            pass

        func()

        self.assertTrue(retry.attempt >= retry.max_attempts)
        self.assertEqual(sleep_mock.call_count, retry.max_attempts)

    def test_does_not_retry_if_predicate_succeeds(self, sleep_mock):
        def always_succeeds():
            return True

        retry = retrying.Retry(max_attempts=5,
                               wait_exponential=True,
                               raise_error=False,
                               predicate=always_succeeds)

        @retry
        def func():
            pass

        func()

        self.assertEqual(retry.attempt, 1)
        self.assertFalse(sleep_mock.called)

    def test_raises_timeout_error_if_timedout(self, sleep_mock):
        retry = retrying.Retry(max_time=100,
                               wait_exponential=True,
                               reraise_original_exception=False)

        @retry
        def func():
            raise RuntimeError()

        self.assertRaises(retrying.TimeoutExceeded, func)
        self.assertTrue(retry.total_time >= retry.max_time)
        self.assertTrue(sleep_mock.called)

    def test_stops_if_retval_matches_predicate(self, sleep_mock):
        def func():
            return 0

        retry = retrying.Retry(max_attempts=5,
                               predicate_retval_as_arg=True,
                               predicate=lambda rv: rv == 0)

        retry.run(func)
        self.assertEqual(retry.attempt, 1)
        self.assertFalse(sleep_mock.called)

    def test_raises_error_if_predicate_failed_after_timeout(self, sleep_mock):
        def func():
            return 0

        retry = retrying.Retry(max_time=100,
                               predicate_retval_as_arg=True,
                               predicate=lambda rv: rv == 1)

        self.assertRaises(retrying.TimeoutExceeded, retry.run, func)
        self.assertTrue(retry.total_time >= retry.max_time)
        self.assertTrue(sleep_mock.called)

    def test_returns_object_returned_by_function(self, sleep_mock):
        expected_rv = 0

        def func():
            return expected_rv

        retry = retrying.Retry(max_attempts=10,
                               predicate_retval_as_arg=True,
                               predicate=lambda rv: rv == expected_rv)

        actual_rv = retry.run(func)
        self.assertEqual(1, retry.attempt)
        self.assertEqual(expected_rv, actual_rv)
        self.assertFalse(sleep_mock.called)

    def test_max_attempt_reached_not_raised_for_multiple_runs(self,
                                                              sleep_mock):
        predicate = mock.Mock()

        @retrying.retry(max_attempts=2, predicate=predicate)
        def foo():
            return 'fake'

        for _ in range(5):
            predicate.side_effect = (False, True)
            sleep_mock.reset_mock()
            self.assertEqual('fake', foo())
            self.assertCalledOnce(sleep_mock)
