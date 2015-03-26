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

from oslotest import mockpatch

from cloudferrylib.scheduler import cursor
from cloudferrylib.scheduler import scheduler
from cloudferrylib.scheduler import task

from tests import test


class WrapThreadTaskFake(mock.MagicMock):
    __name__ = 'WrapThreadTask'

    def __repr__(self):
        return "WrapThreadTask|FakeTask"


class BaseTaskFake(mock.MagicMock):
    __name__ = 'WrapThreadTask'

    def __repr__(self):
        return "BaseTask|FakeTask"


class SchedulerTestCase(test.TestCase):
    def setUp(self):
        super(SchedulerTestCase, self).setUp()
        self.fake_cursor = mock.MagicMock()
        self.cursor_patch = mockpatch.PatchObject(scheduler, 'Cursor',
                                                  new=self.fake_cursor)
        self.useFixture(self.cursor_patch)

        self.fake_process = mock.MagicMock()
        self.process_patch = mockpatch.PatchObject(scheduler, 'WrapThreadTask',
                                                   new=self.fake_process)
        self.useFixture(self.process_patch)
        self.fake_wrap_tt = WrapThreadTaskFake()
        self.wrap_tt_patch = mockpatch.PatchObject(scheduler, 'WrapThreadTask',
                                                   new=self.fake_wrap_tt)
        self.useFixture(self.wrap_tt_patch)
        self.fake_base_task = BaseTaskFake()
        self.wrap_base_task = mockpatch.PatchObject(scheduler, 'BaseTask',
                                                    new=self.fake_base_task)
        self.useFixture(self.wrap_base_task)
        self.fake_namespace = mock.MagicMock()
        self.wrap_namespace = mockpatch.PatchObject(scheduler, 'Namespace',
                                                    new=self.fake_namespace)
        self.useFixture(self.wrap_namespace)

    def test_start_scheduler(self):
       fake_cursor = [self.fake_base_task(),
                      self.fake_wrap_tt(),
                      self.fake_base_task()]
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
       self.assertTrue(fake_cursor[0].called)
       self.assertTrue(fake_cursor[2].called)


class MigrationRollbackTestCase(test.TestCase):
    def test_task_is_rolled_back_on_error(self):
        migration = self._mock_out_task(throws_exception=True)
        rollback = self._mock_out_task()

        s = scheduler.Scheduler(migration=[migration], rollback=[rollback])
        s.map_func_task[migration] = s.task_run
        s.map_func_task[rollback] = s.task_run
        s.start()

        assert rollback.run.called

    def test_preparation_step_is_not_rolled_back_and_error_raised(self):
        migration = self._mock_out_task()
        preparation = self._mock_out_task(throws_exception=True)
        rollback = self._mock_out_task()

        s = scheduler.Scheduler(migration=[migration],
                                preparation=[preparation],
                                rollback=[rollback])

        s.map_func_task[preparation] = s.task_run
        s.map_func_task[migration] = s.task_run
        s.map_func_task[rollback] = s.task_run
        s.start()

        assert preparation.run.called
        assert not rollback.run.called
        assert not migration.run.called

    def _mock_out_task(self, throws_exception=False):
        t = task.Task()
        t.run = mock.Mock()
        if throws_exception:
            t.run.side_effect = Exception
        return t
