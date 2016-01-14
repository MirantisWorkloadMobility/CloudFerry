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

from cloudferrylib.utils import utils
from fabric.api import local
from tests import test


class AttributeString(str):
    pass


def create_attribute_string(value, **kwargs):
    string = AttributeString(value)
    for name, value in kwargs.items():
        setattr(string, name, value)
    return string


class ForwardAgentTestCase(test.TestCase):
    @mock.patch('cloudferrylib.utils.utils.local')
    def test_agent_is_already_run_w_keys(self, test_local):
        test_local.side_effect = [
            create_attribute_string(
                '4096 de:3b:90:e1:3e:f7:3e:f5:4b:e3:ca:9f:1c:68:45:fb '
                'test_key_1 (RSA)\n'
                '2048 8a:f7:05:14:f7:3a:9b:28:70:d8:95:6e:df:e9:78:c7 '
                'test_key_2 (RSA)\n',
                succeeded=True),
        ]
        utils.forward_agent(['test_key_1', 'test_key_2'])
        self.assertTrue(
            utils.ensure_ssh_key_added(['test_key_1', 'test_key_2']))

    @mock.patch('cloudferrylib.utils.utils.local')
    def test_agent_is_not_run(self, test_local):
        test_local.side_effect = [
            create_attribute_string(
                'The agent has no identities', succeeded=True),
            create_attribute_string('Agent pid 1234\n/foo/bar',
                                    succeeded=True),
        ]
        utils.forward_agent(['test_key_1', 'test_key_2'])
        self.assertFalse(
            utils.ensure_ssh_key_added(['test_key_1', 'test_key_2']))

    @mock.patch('cloudferrylib.utils.utils.local')
    def test_agent_is_already_run_w_another_key(self, test_local):
        test_local.return_value = local(
            "echo test_session_num test_fingerprint test_key test_type\n",
            capture=True
        )
        test_local.side_effect = [
            create_attribute_string(
                '4096 de:3b:90:e1:3e:f7:3e:f5:4b:e3:ca:9f:1c:68:45:fb '
                'test_key_1 (RSA)\n',
                succeeded=True),
            create_attribute_string('Agent pid 1234\n/foo/bar',
                                    succeeded=True),
        ]
        utils.forward_agent(['test_key_1', 'test_key_2'])
        self.assertFalse(
            utils.ensure_ssh_key_added(['test_key_1', 'test_key_2']))
