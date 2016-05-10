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

from cloudferry import model
from tests.lib.utils import test_local_db


class ExampleReferenced(model.Model):
    object_id = model.PrimaryKey()
    qux = model.Integer(required=True)

    @classmethod
    def create_object(cls, cloud, cloud_obj_id):
        with model.Session() as session:
            session.store(ExampleReferenced.load({
                'object_id': {
                    'cloud': cloud,
                    'id': cloud_obj_id,
                    'type': cls.get_class_qualname(),
                },
                'qux': 1337,
            }))


class ExampleNested(model.Model):
    foo = model.String(required=True)
    ref = model.Dependency(ExampleReferenced, required=True)
    refs = model.Dependency(ExampleReferenced, required=True, many=True)
    ref_none = model.Dependency(ExampleReferenced, missing=None,
                                allow_none=True)
    refs_none = model.Dependency(ExampleReferenced, missing=None,
                                 many=True, allow_none=True)


class Simple(model.Model):
    foo = model.String(required=True)


class Example(model.Model):
    object_id = model.PrimaryKey()
    bar = model.String(required=True)
    baz = model.Nested(ExampleNested)
    ref = model.Dependency(ExampleReferenced, required=True)
    refs = model.Dependency(ExampleReferenced, required=True, many=True)
    ref_none = model.Dependency(ExampleReferenced, missing=None,
                                allow_none=True)
    refs_none = model.Dependency(ExampleReferenced, missing=None,
                                 many=True, allow_none=True)

    count = 0

    @classmethod
    def generate_data(cls, object_id=None, cloud='test_cloud'):
        cls.count += 1
        if object_id is None:
            object_id = uuid.uuid5(uuid.NAMESPACE_DNS, 'test%d' % cls.count)
        ref1 = uuid.uuid5(uuid.NAMESPACE_DNS, 'ref1_%d' % cls.count)
        ref2 = uuid.uuid5(uuid.NAMESPACE_DNS, 'ref2_%d' % cls.count)
        ExampleReferenced.create_object(cloud, str(ref1))
        ExampleReferenced.create_object(cloud, str(ref2))
        return {
            'object_id': {
                'cloud': cloud,
                'id': str(object_id),
                'type': Example.get_class_qualname(),
            },
            'bar': 'some non-random string',
            'baz': {
                'foo': 'other non-random string',
                'ref': {
                    'cloud': cloud,
                    'id': str(ref1),
                    'type': ExampleReferenced.get_class_qualname(),
                },
                'refs': [{
                    'cloud': cloud,
                    'id': str(ref2),
                    'type': ExampleReferenced.get_class_qualname(),
                }],
            },
            'ref': {
                'cloud': cloud,
                'id': str(ref1),
                'type': ExampleReferenced.get_class_qualname(),
            },
            'refs': [{
                'cloud': cloud,
                'id': str(ref2),
                'type': ExampleReferenced.get_class_qualname(),
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

    @staticmethod
    def _make_id(model_class, cloud_obj_id, cloud='test_cloud'):
        return {
            'id': cloud_obj_id,
            'cloud': cloud,
            'type': model_class.get_class_qualname(),
        }

    def test_load(self):
        data = Example.generate_data()
        obj = Example.load(data)
        self._validate_example_obj(
            model.ObjectId(data['object_id']['id'], 'test_cloud'), obj, False)

    def test_non_dirty(self):
        obj = Example.load(Example.generate_data())
        self.assertTrue(obj.is_dirty('objects'))

    def test_simple_dirty(self):
        obj = Example.load(Example.generate_data())
        obj.bar = 'value is changed'
        self.assertTrue(obj.is_dirty('objects'))

    def test_nested_dirty(self):
        obj = Example.load(Example.generate_data())
        obj.baz.foo = 'value is changed'
        self.assertTrue(obj.is_dirty('objects'))

    def test_ref_dirty(self):
        obj = Example.load(Example.generate_data())
        ref_obj = ExampleReferenced.load({
            'object_id': self._make_id(ExampleReferenced, 'hello'),
            'qux': 313373,
        })
        obj.ref = ref_obj
        self.assertTrue(obj.is_dirty('objects'))

    def test_refs_dirty(self):
        obj = Example.load(Example.generate_data())
        ref_obj = ExampleReferenced.load({
            'object_id': self._make_id(ExampleReferenced, 'hello'),
            'qux': 313373,
        })
        obj.refs.append(ref_obj)
        self.assertTrue(obj.is_dirty('objects'))

    def test_nested_ref_dirty(self):
        obj = Example.load(Example.generate_data())
        ref_obj = ExampleReferenced.load({
            'object_id': self._make_id(ExampleReferenced, 'hello'),
            'qux': 313373,
        })
        obj.baz.ref = ref_obj
        self.assertTrue(obj.is_dirty('objects'))

    def test_nested_refs_dirty(self):
        obj = Example.load(Example.generate_data())
        ref_obj = ExampleReferenced.load({
            'object_id': self._make_id(ExampleReferenced, 'hello'),
            'qux': 313373,
        })
        obj.baz.refs.append(ref_obj)
        self.assertTrue(obj.is_dirty('objects'))

    def test_store_retrieve(self):
        orig_obj = Example.load(Example.generate_data())
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
        orig_obj = Example.load(Example.generate_data())
        object_id = orig_obj.object_id
        with model.Session() as session:
            session.store(orig_obj)
            # Validate retrieve working before commit
            self._validate_example_obj(object_id, session.list(Example)[0])
        with model.Session() as session:
            # Validate retrieve working after commit
            self._validate_example_obj(object_id, session.list(Example)[0])

    def test_store_list_cloud(self):
        orig_obj1 = Example.load(Example.generate_data(cloud=self.cloud.name))
        object1_id = orig_obj1.object_id
        orig_obj2 = Example.load(Example.generate_data(cloud=self.cloud2.name))
        object2_id = orig_obj2.object_id
        with model.Session() as session:
            session.store(orig_obj1)
            session.store(orig_obj2)
            # Validate retrieve working before commit
            self._validate_example_obj(object1_id,
                                       session.list(Example, self.cloud)[0])
            self._validate_example_obj(object2_id,
                                       session.list(Example, self.cloud2)[0])
        # Validate retrieve working after commit
        with model.Session() as session:
            self._validate_example_obj(object1_id,
                                       session.list(Example, self.cloud)[0])
        with model.Session() as session:
            self._validate_example_obj(object2_id,
                                       session.list(Example, self.cloud2)[0])

    def test_load_store(self):
        orig_obj = Example.load(Example.generate_data())
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
            object_id = model.PrimaryKey()
            many = model.Nested(Simple, many=True)

        many = ExampleMany.load({
            'object_id': self._make_id(ExampleMany, 'foo'),
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
            object_id = model.PrimaryKey()
            ref = model.Dependency(Example.get_class_qualname())

        with model.Session() as session:
            example = Example.load(Example.generate_data('foo-bar-baz'))
            session.store(example)

        obj = ExampleNameRef.load({
            'object_id': self._make_id(ExampleNameRef, 'ExampleNameRef-1'),
            'ref': self._make_id(Example, 'foo-bar-baz'),
        })
        self.assertIs(Example, obj.ref.get_class())

    def test_nested_sessions(self):
        orig_obj1 = Example.load(Example.generate_data(cloud=self.cloud.name))
        object1_id = orig_obj1.object_id
        orig_obj2 = Example.load(Example.generate_data(cloud=self.cloud2.name))
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
        orig_obj1 = Example.load(Example.generate_data(cloud=self.cloud.name))
        object1_id = orig_obj1.object_id
        orig_obj2 = Example.load(Example.generate_data(cloud=self.cloud2.name))
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
