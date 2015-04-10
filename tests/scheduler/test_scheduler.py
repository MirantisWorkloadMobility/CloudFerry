# Copyright (c) 2014 Mirantis Inc.
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

from cloudferrylib.scheduler import scheduler
from cloudferrylib.scheduler import task

from tests import test


class SchedulerTestCase(test.TestCase):
    def test_start_scheduler(self):
        fake_cursor = [mock_out_task(),
                       mock_out_task(),
                       mock_out_task()]
        s = scheduler.Scheduler(migration=fake_cursor)
        s.event_start_task = mock.Mock()
        s.event_start_task.return_value = True
        s.event_end_task = mock.Mock()
        s.start()
        self.assertEqual(scheduler.NO_ERROR, s.status_error)
        self.assertIsNotNone(s.event_start_task.call_args)
        self.assertIn(fake_cursor[0], s.event_start_task.call_args[0])
        self.assertIsNotNone(s.event_end_task.call_args)
        self.assertIn(fake_cursor[0], s.event_end_task.call_args[0])
        self.assertTrue(fake_cursor[0].run.called)
        self.assertTrue(fake_cursor[2].run.called)


class MigrationRollbackTestCase(test.TestCase):
    def test_task_is_rolled_back_on_error(self):
        migration = mock_out_task(throws_exception=True)
        rollback = mock_out_task()

        s = scheduler.Scheduler(migration=[migration], rollback=[rollback])
        s.start()

        assert rollback.run.called

    def test_preparation_step_is_not_rolled_back_and_error_raised(self):
        migration = mock_out_task()
        preparation = mock_out_task(throws_exception=True)
        rollback = mock_out_task()

        s = scheduler.Scheduler(migration=[migration],
                                preparation=[preparation],
                                rollback=[rollback])

        s.start()

        assert preparation.run.called
        assert not rollback.run.called
        assert not migration.run.called


def mock_out_task(throws_exception=False):
    t = task.Task()
    t.run = mock.Mock()
    if throws_exception:
        t.run.side_effect = Exception
    return t
