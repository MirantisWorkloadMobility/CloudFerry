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
import mock
import uuid

from cloudferrylib.os.discovery import model
from tests.cloudferrylib.utils import test_local_db


class ExampleReferenced(model.Model):
    class Schema(model.Schema):
        object_id = model.PrimaryKey()
        qux = model.fields.Integer(required=True)

    @classmethod
    def load_missing(cls, cloud, object_id):
        result = ExampleReferenced.load({
            'object_id': {
                'cloud': object_id.cloud,
                'id': object_id.id,
                'type': 'tests.cloudferrylib.os.discovery.test_model.'
                        'ExampleReferenced',
            },
            'qux': 1337,
        })
        result.mark_dirty()
        return result


class ExampleNested(model.Model):
    class Schema(model.Schema):
        foo = model.fields.String(required=True)
        ref = model.Dependency(ExampleReferenced, required=True)
        refs = model.Dependency(ExampleReferenced, required=True, many=True)
        ref_none = model.Dependency(ExampleReferenced, missing=None,
                                    allow_none=True)
        refs_none = model.Dependency(ExampleReferenced, missing=None,
                                     many=True, allow_none=True)


class Simple(model.Model):
    class Schema(model.Schema):
        foo = model.fields.String(required=True)


class Example(model.Model):
    class Schema(model.Schema):
        object_id = model.PrimaryKey()
        bar = model.fields.String(required=True)
        baz = model.Nested(ExampleNested)
        ref = model.Dependency(ExampleReferenced, required=True)
        refs = model.Dependency(ExampleReferenced, required=True, many=True)
        ref_none = model.Dependency(ExampleReferenced, missing=None,
                                    allow_none=True)
        refs_none = model.Dependency(ExampleReferenced, missing=None,
                                     many=True, allow_none=True)

    count = 0

    @classmethod
    def load_missing(cls, cloud, object_id):
        return Example.load_from_cloud(cloud, cls.generate_cloud_data())

    @classmethod
    def generate_cloud_data(cls):
        cls.count += 1
        object_id = uuid.uuid5(uuid.NAMESPACE_DNS, 'test%d' % cls.count)
        ref1 = uuid.uuid5(uuid.NAMESPACE_DNS, 'ref1_%d' % cls.count)
        ref2 = uuid.uuid5(uuid.NAMESPACE_DNS, 'ref2_%d' % cls.count)
        return {
            'object_id': str(object_id),
            'bar': 'some non-random string',
            'ref': str(ref1),
            'refs': [str(ref2)],
            'baz': {
                'foo': 'other non-random string',
                'ref': str(ref1),
                'refs': [str(ref2)],
            },
        }

    @classmethod
    def generate_clean_data(cls):
        cls.count += 1
        object_id = uuid.uuid5(uuid.NAMESPACE_DNS, 'test%d' % cls.count)
        ref1 = uuid.uuid5(uuid.NAMESPACE_DNS, 'ref1_%d' % cls.count)
        ref2 = uuid.uuid5(uuid.NAMESPACE_DNS, 'ref2_%d' % cls.count)
        return {
            'object_id': {
                'cloud': 'test_cloud',
                'id': str(object_id),
                'type': 'tests.cloudferrylib.os.discovery.test_model.Example',
            },
            'bar': 'some non-random string',
            'baz': {
                'foo': 'other non-random string',
                'ref': {
                    'cloud': 'test_cloud',
                    'id': str(ref1),
                    'type': 'tests.cloudferrylib.os.discovery.test_model.'
                            'ExampleReferenced',
                },
                'refs': [{
                    'cloud': 'test_cloud',
                    'id': str(ref2),
                    'type': 'tests.cloudferrylib.os.discovery.test_model.'
                            'ExampleReferenced',
                }],
            },
            'ref': {
                'cloud': 'test_cloud',
                'id': str(ref1),
                'type': 'tests.cloudferrylib.os.discovery.test_model.'
                        'ExampleReferenced',
            },
            'refs': [{
                'cloud': 'test_cloud',
                'id': str(ref2),
                'type': 'tests.cloudferrylib.os.discovery.test_model.'
                        'ExampleReferenced',
            }],
        }


class ModelTestCase(test_local_db.DatabaseMockingTestCase):
    def setUp(self):
        super(ModelTestCase, self).setUp()

        self.cloud = mock.MagicMock()
        self.cloud.name = 'test_cloud'

        self.cloud2 = mock.MagicMock()
        self.cloud2.name = 'test_cloud2'

    def _validate_example_obj(self, object_id, obj, validate_refs=True,
                              bar_value='some non-random string'):
        self.assertEqual(object_id, obj.object_id)
        self.assertEqual(bar_value, obj.bar)
        self.assertEqual('other non-random string', obj.baz.foo)
        if validate_refs:
            self.assertEqual(1337, obj.ref.qux)
            self.assertEqual(1337, obj.refs[0].qux)

    def test_load_from_cloud(self):
        data = Example.generate_cloud_data()
        obj = Example.load_from_cloud(self.cloud, data)
        self._validate_example_obj(
            model.ObjectId(data['object_id'], 'test_cloud'), obj)

    def test_load(self):
        data = Example.generate_clean_data()
        obj = Example.load(data)
        self._validate_example_obj(
            model.ObjectId(data['object_id']['id'], 'test_cloud'), obj, False)

    def test_non_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        self.assertFalse(obj.is_dirty())

    def test_simple_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        obj.bar = 'value is changed'
        self.assertTrue(obj.is_dirty())

    def test_nested_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        obj.baz.foo = 'value is changed'
        self.assertTrue(obj.is_dirty())

    def test_ref_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        ref_obj = ExampleReferenced.load_from_cloud(self.cloud, {
            'object_id': 'hello',
            'qux': 313373,
        })
        obj.ref = ref_obj
        self.assertTrue(obj.is_dirty())

    def test_refs_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        ref_obj = ExampleReferenced.load_from_cloud(self.cloud, {
            'object_id': 'hello',
            'qux': 313373,
        })
        obj.refs.append(ref_obj)
        self.assertTrue(obj.is_dirty())

    def test_nested_ref_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        ref_obj = ExampleReferenced.load_from_cloud(self.cloud, {
            'object_id': 'hello',
            'qux': 313373,
        })
        obj.baz.ref = ref_obj
        self.assertTrue(obj.is_dirty())

    def test_nested_refs_dirty(self):
        obj = Example.load(Example.generate_clean_data())
        ref_obj = ExampleReferenced.load_from_cloud(self.cloud, {
            'object_id': 'hello',
            'qux': 313373,
        })
        obj.baz.refs.append(ref_obj)
        self.assertTrue(obj.is_dirty())

    def test_store_retrieve(self):
        data = Example.generate_cloud_data()
        orig_obj = Example.load_from_cloud(self.cloud, data)
        object_id = orig_obj.object_id
        with model.Session() as session:
            session.store(orig_obj)
            # Validate retrieve working before commit
            self._validate_example_obj(
                object_id, session.retrieve(Example, object_id))
        with model.Session() as session:
            # Validate retrieve working after commit
            self._validate_example_obj(
                object_id, session.retrieve(Example, object_id))

    def test_store_list(self):
        data = Example.generate_cloud_data()
        orig_obj = Example.load_from_cloud(self.cloud, data)
        object_id = orig_obj.object_id
        with model.Session() as session:
            session.store(orig_obj)
            # Validate retrieve working before commit
            self._validate_example_obj(object_id, session.list(Example)[0])
        with model.Session() as session:
            # Validate retrieve working after commit
            self._validate_example_obj(object_id, session.list(Example)[0])

    def test_store_list_cloud(self):
        data = Example.generate_cloud_data()
        orig_obj1 = Example.load_from_cloud(self.cloud, data)
        object1_id = orig_obj1.object_id
        orig_obj2 = Example.load_from_cloud(self.cloud2, data)
        object2_id = orig_obj2.object_id
        with model.Session() as session:
            session.store(orig_obj1)
            session.store(orig_obj2)
            # Validate retrieve working before commit
            self._validate_example_obj(object1_id,
                                       session.list(Example, 'test_cloud')[0])
            self._validate_example_obj(object2_id,
                                       session.list(Example, 'test_cloud2')[0])
        # Validate retrieve working after commit
        with model.Session() as session:
            self._validate_example_obj(object1_id,
                                       session.list(Example, 'test_cloud')[0])
        with model.Session() as session:
            self._validate_example_obj(object2_id,
                                       session.list(Example, 'test_cloud2')[0])

    def test_load_store(self):
        data = Example.generate_cloud_data()
        orig_obj = Example.load_from_cloud(self.cloud, data)
        object_id = orig_obj.object_id
        with model.Session() as session:
            session.store(orig_obj)
        with model.Session() as session:
            obj = session.retrieve(Example, object_id)
            self._validate_example_obj(object_id, obj)
            obj.baz.foo = 'changed'
            obj.bar = 'changed too'
        with model.Session() as session:
            loaded_obj = session.retrieve(Example, object_id)
            self.assertEqual('changed', loaded_obj.baz.foo)
            self.assertEqual('changed too', loaded_obj.bar)

    def test_many_nested(self):
        class ExampleMany(model.Model):
            class Schema(model.Schema):
                object_id = model.PrimaryKey()
                many = model.Nested(Simple, many=True)

        many = ExampleMany.load_from_cloud(self.cloud, {
            'object_id': 'foo',
            'many': [
                {'foo': 'foo'},
                {'foo': 'bar'},
                {'foo': 'baz'},
            ],
        })
        self.assertEqual('foo', many.many[0].foo)
        self.assertEqual('bar', many.many[1].foo)
        self.assertEqual('baz', many.many[2].foo)
        with model.Session() as session:
            session.store(many)

        with model.Session() as session:
            obj = session.retrieve(
                ExampleMany, model.ObjectId('foo', 'test_cloud'))
            self.assertEqual('foo', obj.many[0].foo)
            self.assertEqual('bar', obj.many[1].foo)
            self.assertEqual('baz', obj.many[2].foo)

    def test_example_name_ref(self):
        class ExampleNameRef(model.Model):
            class Schema(model.Schema):
                object_id = model.PrimaryKey()
                ref = model.Dependency('tests.cloudferrylib.os.'
                                       'discovery.test_model.Example')

        obj = ExampleNameRef.load_from_cloud(self.cloud, {
            'object_id': 'ExampleNameRef-1',
            'ref': str('foo-bar-baz'),
        })
        self.assertIs(Example, obj.ref.get_class())

    def test_nested_sessions(self):
        data = Example.generate_cloud_data()
        orig_obj1 = Example.load_from_cloud(self.cloud, data)
        object1_id = orig_obj1.object_id
        orig_obj2 = Example.load_from_cloud(self.cloud2, data)
        object2_id = orig_obj2.object_id

        with model.Session() as s1:
            s1.store(orig_obj1)
            with model.Session() as s2:
                s2.store(orig_obj2)
                self._validate_example_obj(
                    object1_id, s2.retrieve(Example, object1_id))
                self._validate_example_obj(
                    object2_id, s2.retrieve(Example, object2_id))
        with model.Session() as s:
            self._validate_example_obj(
                object1_id, s.retrieve(Example, object1_id))
            self._validate_example_obj(
                object2_id, s2.retrieve(Example, object2_id))

    def test_nested_sessions_save_updates_after_nested(self):
        data = Example.generate_cloud_data()
        orig_obj1 = Example.load_from_cloud(self.cloud, data)
        object1_id = orig_obj1.object_id
        orig_obj2 = Example.load_from_cloud(self.cloud2, data)
        object2_id = orig_obj2.object_id

        with model.Session() as s1:
            s1.store(orig_obj1)
            with model.Session() as s2:
                s2.store(orig_obj2)
                self._validate_example_obj(
                    object1_id, s2.retrieve(Example, object1_id))
                self._validate_example_obj(
                    object2_id, s2.retrieve(Example, object2_id))
            orig_obj1.bar = 'some other non-random string'
        with model.Session() as s:
            self._validate_example_obj(
                object1_id, s.retrieve(Example, object1_id),
                bar_value='some other non-random string')
            self._validate_example_obj(
                object2_id, s2.retrieve(Example, object2_id))
