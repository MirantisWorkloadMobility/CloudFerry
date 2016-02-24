# Copyright 2014: Mirantis Inc.
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

from oslotest import base

import cfglib


class TestCase(base.BaseTestCase):
    """Test case base class for all unit tests."""

    def setUp(self):
        super(TestCase, self).setUp()
        self.addCleanup(mock.patch.stopall)
        self.cfg = cfglib.CONF
        self.addCleanup(self.cfg.reset)
        cfglib.init_config()

    def assertIsZero(self, observed, message=''):
        self.assertEqual(0, observed, message)

    def assertCalledOnce(self, mock_obj, message=''):
        message = message or ("Expected '%s' to be called once. "
                              "Called %s times." % (mock_obj,
                                                    mock_obj.call_count))
        self.assertEqual(1, mock_obj.call_count, message)
