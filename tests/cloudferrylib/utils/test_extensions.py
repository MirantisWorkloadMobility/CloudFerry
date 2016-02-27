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
from cloudferrylib.utils import extensions
from cloudferrylib.os.storage.plugins import base
from tests import test

OS_STORAGE_PLUGINS = 'cloudferrylib.os.storage.plugins'


class PluginLoaderTestCase(test.TestCase):
    def test_returns_list(self):
        self.assertIsInstance(
            extensions.available_extensions(base.CinderMigrationPlugin,
                                            OS_STORAGE_PLUGINS), list)

    def test_plugins_are_inherited_from_base(self):
        self.assertTrue(all((issubclass(p, base.CinderMigrationPlugin)
                             for p in extensions.available_extensions(
                base.CinderMigrationPlugin, OS_STORAGE_PLUGINS))))
