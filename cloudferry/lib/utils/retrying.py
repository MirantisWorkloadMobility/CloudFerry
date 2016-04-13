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

import logging
import sys
import time
from functools import wraps

LOG = logging.getLogger(__name__)


UNLIMITED = object()


class RetryError(RuntimeError):
    pass


class RetryRequired(RetryError):
    pass


class TimeoutExceeded(RetryError):
    pass


class MaxAttemptsReached(RetryError):
    pass


class Retry(object):
    """Retries method calls based on configuration provided

     :param max_attempts: maximum number of attempts to retry
     :param max_time: maximum time to wait
     :param wait_exponential: sleep time will grow exponentially if set to
     true, linear otherwise. Exponent factor is 2.
     :param raise_error: when set to True - raises error if all attempts
     failed otherwise continues silently
     :param reraise_original_exception: if set to True, re-raises last
     exception of function instead of MaxAttemptsReached or TimeoutException.
     :param retry_on_return_value: retries if return value matches to
     `return_value`
     :param return_value: see :param retry_on_return_value:
     :param timeout: sleep timeout when :param wait_exponential: is disabled
     :param expected_exceptions: list of exceptions which will be ignored
     and raised to user without sleep
     :param predicate: predicate to check after each function call
     :param predicate_args: predicate arguments
     :param predicate_kwargs: predicate key-value arguments
     :param predicate_retval_as_arg: use function's return value as argument
     to predicate
     :param retry_message: message to be printed into log on each failure
     :param stop_on_return_value: retries are stopped when return value matches
     :param print_stack_trace: logs traceback on each failure if set to true
    """

    def __init__(self,
                 max_attempts=1,
                 max_time=UNLIMITED,
                 wait_exponential=True,
                 raise_error=True,
                 reraise_original_exception=False,
                 retry_on_return_value=False,
                 return_value=None,
                 timeout=1,
                 expected_exceptions=None,
                 predicate=None,
                 predicate_args=None,
                 predicate_kwargs=None,
                 predicate_retval_as_arg=False,
                 retry_message=None,
                 stop_on_return_value=False,
                 print_stack_trace=False):
        self.print_stack_trace = print_stack_trace
        self.reraise_original_exception = reraise_original_exception
        self.timeout = timeout
        self.total_time = 0
        self.attempt = 0
        self.max_attempts = max_attempts
        self.wait_exponential = wait_exponential
        self.max_time = max_time
        self.raise_error = raise_error
        self.retry_on_return_value = retry_on_return_value
        self.return_value = return_value
        self.expected_exceptions = tuple(expected_exceptions or [])
        self.predicate = predicate
        self.predicate_args = predicate_args
        self.predicate_kwargs = predicate_kwargs
        self.predicate_retval_as_arg = predicate_retval_as_arg
        self.retry_message = retry_message
        self.stop_on_return_value = stop_on_return_value

    def max_attempts_reached(self):
        return self.attempt >= self.max_attempts

    def increment_attempts(self):
        self.attempt += 1

    def reset_attempts(self):
        self.attempt = 0

    def reset_total_time(self):
        self.total_time = 0

    def timedout(self):
        return self.total_time >= self.max_time

    def update_total_time(self):
        if self.wait_exponential:
            self.timeout *= 2

        self.total_time += self.timeout

    def sleep(self):
        time.sleep(self.timeout)

    def get_retry_message(self, auto_message):
        if self.retry_message:
            return self.retry_message
        else:
            return auto_message

    def handle_predicate(self, retval):
        if self.predicate and callable(self.predicate):
            if self.predicate_retval_as_arg:
                args = [retval]
            else:
                args = self.predicate_args or []
            kwargs = self.predicate_kwargs or {}
            if not self.predicate(*args, **kwargs):
                default_msg = "Function exited with '{}'".format(retval)
                msg = self.get_retry_message(default_msg)
                raise RetryRequired(msg)

    def handle_return_on_value(self, retval):
        if self.stop_on_return_value and retval != self.return_value:
            msg = "Return value '{}' didn't match expected '{}'"
            raise RetryRequired(msg.format(retval, self.return_value))

        if self.retry_on_return_value and retval == self.return_value:
            msg = self.get_retry_message(
                "Unexpected return value: {}".format(retval))
            raise RetryRequired(msg)

    def run(self, func, *args, **kwargs):
        stop_retrying = self.max_attempts_reached
        step_action = self.increment_attempts
        reset_retrying = self.reset_attempts

        if self.max_time is not UNLIMITED:
            stop_retrying = self.timedout
            step_action = self.update_total_time
            reset_retrying = self.reset_total_time

        retval = None
        failing = True
        last_exception = None

        reset_retrying()
        while failing and not stop_retrying():
            step_action()
            try:
                retval = func(*args, **kwargs)

                self.handle_predicate(retval)
                self.handle_return_on_value(retval)

                failing = False
            except Exception as e:  # pylint: disable=broad-except
                if isinstance(e, self.expected_exceptions):
                    raise
                last_exception = sys.exc_info()
                LOG.debug("%s, retrying", e, exc_info=self.print_stack_trace)
                self.sleep()

        if self.raise_error and failing:
            if self.reraise_original_exception and last_exception is not None:
                raise last_exception[0], last_exception[1], last_exception[2]
            else:
                if stop_retrying == self.timedout:
                    raise TimeoutExceeded("Max timeout exceeded")
                elif stop_retrying == self.max_attempts_reached:
                    raise MaxAttemptsReached("Max attempts reached")

        return retval

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            return self.run(func, *args, **kwargs)

        return wrapped


retry = Retry
