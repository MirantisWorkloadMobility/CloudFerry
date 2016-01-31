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
from mock import mock

from tests import test
from cloudferrylib.base.action import get_info_iter


class MigrationProgressViewTestCase(test.TestCase):
    def test_all_objects_length_is_all_objects_plus_one(self):
        # all_objects contents are controlled outside of MigrationProgressView
        # and first object is popped before first use of show_progress(),
        # thus the need in N+1 length.

        log = mock.Mock()
        all_objects = {
            'o1': 'v1',
            'o2': 'v2',
            'o3': 'v3'
        }

        mpv = get_info_iter.MigrationProgressView('instance', output=log)

        mpv.show_progress(mock.Mock(), all_objects)

        self.assertEqual(mpv.total, len(all_objects) + 1)

    def test_info_displayed_if_at_least_one_object_present(self):
        log = mock.Mock()
        all_objects = {
            'o1': 'v1'
        }

        mpv = get_info_iter.MigrationProgressView('instance', output=log)

        mpv.show_progress(mock.Mock(), all_objects)

        self.assertTrue(log.info.called)
