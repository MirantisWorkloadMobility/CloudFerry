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
from mock import patch

from cloudferrylib.utils import qemu_img

from tests import test


class QemuImgCommandsTestCase(test.TestCase):
    @patch("cloudferrylib.utils.remote_runner.RemoteRunner")
    def test_backing_file_returns_none_if_not_available(self, _):
        cloud = mock.Mock()
        config = mock.Mock()
        host = mock.Mock()
        ephemeral = mock.Mock()

        qi = qemu_img.QemuImg(cloud, config, host)
        backing_file = qi.detect_backing_file(ephemeral, host)
        self.assertIsNone(backing_file)

    @patch("cloudferrylib.utils.remote_runner.RemoteRunner.run")
    def test_backing_file_returned_for_good_ephemeral(self, runner):
        cloud = mock.Mock()
        config = mock.Mock()
        host = "host1"
        ephemeral = "disk"
        expected_backing = "/path/to/backing/file"

        # dict is based on the actual output of qemu-img utility
        runner.return_value = """{{
            "virtual-size": 1073741824,
            "filename": "disk",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 1974272,
            "format-specific": {{
                "type": "qcow2",
                "data": {{
                    "compat": "1.1",
                    "lazy-refcounts": false
                }}
            }},
            "backing-filename": "{backing_file}",
            "dirty-flag": false
        }}""".format(backing_file=expected_backing)

        qi = qemu_img.QemuImg(cloud, config, host)

        actual_backing = qi.detect_backing_file(ephemeral, host)

        self.assertEqual(expected_backing, actual_backing)
