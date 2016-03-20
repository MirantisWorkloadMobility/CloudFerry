# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from cloudferrylib import stage

from tests.cloudferrylib.utils import test_local_db

import mock

call_checker = None


def fqname(cls):
    return cls.__module__ + '.' + cls.__name__


class TestStage(stage.Stage):
    def __init__(self):
        self.invalidated = False

    def signature(self, config):
        return config

    def execute(self, config):
        self._execute(config, self.invalidated)

    def invalidate(self, old_signature, new_signature, force=False):
        self._invalidate(old_signature, new_signature)
        self.invalidated = True

    def _execute(self, config, invalidated):
        pass

    def _invalidate(self, old_signature, new_signature):
        pass


class StageOne(TestStage):
    pass


class StageTwo(TestStage):
    dependencies = [
        fqname(StageOne)
    ]


class StageTestCase(test_local_db.DatabaseMockingTestCase):
    def setUp(self):
        super(StageTestCase, self).setUp()
        self.config1 = {'marker': 1}
        self.config2 = {'marker': 2}

    @mock.patch.object(StageOne, '_execute')
    def test_dependencies_execute(self, execute):
        stage.execute_stage(fqname(StageOne), self.config1)
        execute.assert_called_once_with(self.config1, False)

    @mock.patch.object(StageOne, '_execute')
    @mock.patch.object(StageTwo, '_execute')
    def test_dependencies_execute_once(self, execute_two, execute_one):
        stage.execute_stage(fqname(StageOne), self.config1)
        stage.execute_stage(fqname(StageTwo), self.config1)
        execute_one.assert_called_once_with(self.config1, False)
        execute_two.assert_called_once_with(self.config1, False)

    @mock.patch.object(StageOne, '_execute')
    @mock.patch.object(StageTwo, '_execute')
    def test_dependencies_execute_deps(self, execute_two, execute_one):
        stage.execute_stage(fqname(StageTwo), self.config1)
        execute_one.assert_called_once_with(self.config1, False)
        execute_two.assert_called_once_with(self.config1, False)

    @mock.patch.object(StageOne, '_invalidate')
    @mock.patch.object(StageOne, '_execute')
    @mock.patch.object(StageTwo, '_execute')
    def test_invalidate_dependencies_on_configuration_change(
            self, execute_two, execute_one, invalidate_one):
        stage.execute_stage(fqname(StageOne), self.config1)
        stage.execute_stage(fqname(StageTwo), self.config2)
        execute_one.assert_has_calls([
            mock.call(self.config1, False),
            mock.call(self.config2, True),
        ])
        execute_two.assert_called_once_with(self.config2, False)
        invalidate_one.assert_called_once_with(self.config1, self.config2)
