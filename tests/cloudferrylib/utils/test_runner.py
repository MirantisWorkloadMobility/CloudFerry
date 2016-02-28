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

import mock

from cloudferrylib.utils import remote_runner

from tests import test


class RemoteRunnerTestCase(test.TestCase):
    def test_remote_runner_raises_error_if_errors_are_not_ignored(self):
        rr = remote_runner.RemoteRunner('host', 'user', 'password',
                                        ignore_errors=False)

        self.assertRaises(remote_runner.RemoteExecutionError, rr.run,
                          "non existing failing command")

    @mock.patch('cloudferrylib.utils.utils.forward_agent')
    @mock.patch('fabric.api.sudo')
    @mock.patch('fabric.api.settings')
    def test_errors_are_suppressed_for_run_ignoring_errors(
            self, *_):
        rr = remote_runner.RemoteRunner('host', 'user', 'password', sudo=True,
                                        ignore_errors=False)

        try:
            rr.run_ignoring_errors("failing command")

            self.assertFalse(rr.ignore_errors)
        except remote_runner.RemoteExecutionError as e:
            self.fail("run_ignoring_errors must not raise exceptions: %s" % e)

    @mock.patch('cloudferrylib.utils.utils.forward_agent')
    @mock.patch('fabric.api.sudo')
    @mock.patch('fabric.api.run')
    def test_root_user_does_not_sudo(self, _, sudo, run):
        rr = remote_runner.RemoteRunner('host', 'root',
                                        key='key', sudo=True,
                                        ignore_errors=False)
        rr.run('cmd')

        assert not sudo.called
        assert run.called
