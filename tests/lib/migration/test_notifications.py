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
from tests import test

from cloudferry.lib.migration import notifiers
from cloudferry.lib.migration import objects
from cloudferry.lib.migration import observers


class MigrationNotifierTestCase(test.TestCase):
    def test_keeps_all_appended_messages(self):
        obj = {'id': 'some_uuid', 'name': 'name'}
        num_messages = 10

        o = observers.MemoizingMigrationObserver()
        n = notifiers.MigrationStateNotifier()
        n.add_observer(o)

        type_vm = objects.MigrationObjectType.VM
        for i in xrange(num_messages):
            n.append_message(type_vm, obj, '{:d}'.format(i))

        obj = o.get_object(type_vm, obj)
        if obj is None:
            self.fail("Observer must have object stored")

        for i in xrange(num_messages):
            self.assertIn(str(i), obj.message)

    def test_updates_object_state(self):
        src_obj = {'id': 'src_uuid'}
        dst_uuid = 'dst_uuid'

        o = observers.MemoizingMigrationObserver()
        n = notifiers.MigrationStateNotifier()
        n.add_observer(o)

        type_vm = objects.MigrationObjectType.VM
        n.success(type_vm, src_obj, dst_uuid,
                  message=objects.MigrationState.SUCCESS)

        obj = o.get_object(type_vm, src_obj)
        if obj is None:
            self.fail("Observer must have object stored")

        self.assertEqual(src_obj['id'], obj.uuid)
        self.assertEqual(dst_uuid, obj.dst_uuid)
        self.assertEqual(objects.MigrationState.SUCCESS, obj.state)
        self.assertEqual(objects.MigrationState.SUCCESS, obj.message)

        n.fail(type_vm, src_obj, message=objects.MigrationState.FAILURE)
        self.assertEqual(src_obj['id'], obj.uuid)
        self.assertEqual(dst_uuid, obj.dst_uuid)
        self.assertEqual(objects.MigrationState.FAILURE, obj.state)
        self.assertEqual(objects.MigrationState.FAILURE, obj.message)

        n.skip(type_vm, src_obj, message=objects.MigrationState.SKIPPED)
        self.assertEqual(src_obj['id'], obj.uuid)
        self.assertEqual(dst_uuid, obj.dst_uuid)
        self.assertEqual(objects.MigrationState.SKIPPED, obj.state)
        self.assertEqual(objects.MigrationState.SKIPPED, obj.message)
