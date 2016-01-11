# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import mock

from cloudferrylib.base import exception
from cloudferrylib.base import resource

from tests import test

t_exc = exception.TimeoutException


class ResourceTestCase(test.TestCase):
    def setUp(self):
        super(ResourceTestCase, self).setUp()
        self.fake_get_status = mock.Mock()
        self.fake_get_status.return_value = 'online'
        self.res = resource.Resource()

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    def test_wait_for_status_raised_exc(self, mock_sleep):
        self.assertRaises(t_exc, self.res.wait_for_status, 1,
                          self.fake_get_status, 'offline', 3)
        mock_sleep.assert_called_with(2)

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    def test_wait_for_status(self, mock_sleep):
        try:
            self.res.wait_for_status(1, self.fake_get_status, 'online')
        except t_exc as e:
            self.fail(e)
        self.fake_get_status.assert_called_once_with(1)
        if mock_sleep.called:
            self.fail('Sleep has been called')

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    def test_try_wait_for_status_not_raised_exc(self, mock_sleep):
        try:
            self.res.try_wait_for_status(1, self.fake_get_status, 'offline', 3)
        except t_exc as e:
            self.fail(e)
        self.fake_get_status.assert_called_with(1)
        if not mock_sleep.called:
            self.fail('Sleep has not been called')

    @mock.patch('cloudferrylib.base.resource.time.sleep')
    def test_try_wait_for_status(self, mock_sleep):
        try:
            self.res.try_wait_for_status(1, self.fake_get_status, 'online', 3)
        except t_exc as e:
            self.fail(e)
        self.fake_get_status.assert_called_once_with(1)
        if mock_sleep.called:
            self.fail('Sleep has been called')
