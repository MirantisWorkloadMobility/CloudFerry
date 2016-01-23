# Copyright (c) 2016 Mirantis Inc.
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

import contextlib
import mock

from cloudferrylib.copy_engines import base
from cloudferrylib.utils import remote_runner

from tests import test


class BaseTestCase(test.TestCase):
    copier_class = None

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.src_cloud = mock.Mock()
        self.dst_cloud = mock.Mock()
        self.copier = self.copier_class(  # pylint: disable=not-callable
            self.src_cloud, self.dst_cloud)
        self.data = {
            'host_src': 'fake_host_src',
            'path_src': 'fake_path_src',
            'host_dst': 'fake_host_dst',
            'path_dst': 'fake_path_dst',
        }

    @contextlib.contextmanager
    def mock_runner(self):
        with mock.patch.object(self.copier, 'runner') as runner:
            yield runner()


class BaseCopierTestCase(BaseTestCase):
    copier_class = base.BaseCopier

    def test_runner(self):
        runner = self.copier.runner('fake_host', 'src')
        self.assertIsInstance(runner, remote_runner.RemoteRunner)

    def test_runner_cache(self):
        runner1 = self.copier.runner('fake_host', 'src')
        runner2 = self.copier.runner('fake_host', 'src')
        runner3 = self.copier.runner('fake_host', 'dst')

        self.assertEqual(runner1, runner2)
        self.assertIsNot(runner3, runner1)

    def test_check_usage(self):
        self.assertTrue(self.copier.check_usage(self.data))

    def test_get_name(self):
        self.assertIsNone(self.copier.name)
        self.assertEqual(self.copier.__class__.__name__,
                         self.copier.get_name())

        self.copier.__class__.name = 'fake_name'
        self.assertEqual('fake_name', self.copier.get_name())
        self.copier.__class__.name = None

    def test_clean_dst(self):
        with self.mock_runner() as runner:
            self.copier.clean_dst(self.data)
            self.assertCalledOnce(runner.run_ignoring_errors)


class FakeCopier(base.BaseCopier):
    name = 'fake'

    def transfer(self, data):
        pass


class GetCopierTestCase(test.TestCase):
    def setUp(self):
        super(GetCopierTestCase, self).setUp()
        m = mock.patch(
            'cloudferrylib.utils.extensions.available_extensions',
            return_value=[FakeCopier])
        self.copiers = m.start()
        self.addCleanup(m.stop)

    def test_get_copier_class(self):
        self.assertIs(FakeCopier, base.get_copier_class('fake'))

    def test_get_copier_class_not_found(self):
        self.assertRaises(base.CopierNotFound, base.get_copier_class,
                          'fake_fake')

    def get_copier(self, name):
        self.cfg.set_override('copy_backend', name, 'migrate')
        return base.get_copier('fake_src_cloud', 'fake_dst_cloud',
                               {'host_src': 'fake_host_src',
                                'host_dst': 'fake_host_dst'})

    def test_get_copier(self):
        self.assertIsInstance(self.get_copier('fake'), FakeCopier)

    def test_get_copier_not_found(self):
        self.assertRaises(base.CopierNotFound, self.get_copier, 'fake_fake')

    def test_get_copier_cannot_be_used(self):
        with mock.patch.object(FakeCopier, 'check_usage', return_value=False):
            self.assertRaises(base.CopierCannotBeUsed, self.get_copier, 'fake')
