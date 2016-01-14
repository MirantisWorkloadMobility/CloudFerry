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
"""
Model module contain tools to define cloud object schema and a way to store
this objects in database.

Each model can define classmethod used to discover objects defined by model
(``Model.discover(cloud)``) and classmethod used to retrieve object from cloud
when there is reference/dependency pointing to it but it's not available in the
database (``Model.load_missing(cloud)``).

When creating objects based on some dictionary or object returned by OpenStack
API ``Model.load_from_cloud(cloud, data)`` classmethod should be used as this
allows to convert some attributes to representation that is used to store
it to database like renaming attribute names and ensuring that dependency
object exists in database (and retrieve it from cloud if it's not).

In order to map OpenStack API object attribute names (like
``os-vol-host-attr:host``) to something more human-friendly and compact (like
``host``) ``FIELD_MAPPING`` dictionary can be used: keys represent final
attribute names and values represent source attribute names.

Example defining cloud object schema::

    from marshmallow import fields
    from cloudferrylib.os.discovery import model
    from cloudferrylib.os.discovery import nova


    class Attachment(model.Model):
        class Schema(model.Schema):
            server = fields.Reference(nova.Server, required=True)
            device = fields.String(required=True)


    class Volume(model.Model):
        class Schema(model.Schema):
            object_id = model.PrimaryKey('id')
            name = fields.String(required=True)
            encrypted = fields.Boolean(missing=False)
            size = fields.Integer(required=True)
            tenant = model.Dependency(keystone.Tenant, required=True)
            metadata = fields.Dict(missing=dict)
            attachments = model.Nested(Attachment, many=True, missing=list)

            FIELD_MAPPING = {
                'name': 'display_name',
                'description': 'display_description',
                'host': 'os-vol-host-attr:host',
                'tenant': 'os-vol-tenant-attr:tenant_id',
            }

        @classmethod
        def load_missing(cls, cloud, object_id):
            volume_client = cloud.volume_client()
            raw_volume = volume_client.volumes.get(object_id.id)
            return Volume.load_from_cloud(cloud, raw_volume)

        @classmethod
        def discover(cls, cloud):
            volume_client = cloud.volume_client()
            volumes_list = volume_client.volumes.list(
                search_opts={'all_tenants': True})
            with model.Transaction() as tx:
                for raw_volume in volumes_list:
                    volume = Volume.load_from_cloud(cloud, raw_volume)
                    tx.store(volume)


Example using ``Transaction`` class to store and retrieve data from database::

    from cloudferrylib.os.discovery import model


    class Tenant(model.Model):
        class Schema(model.Schema):
            object_id = model.PrimaryKey('id')
            name = fields.String(required=True)

    # Storing new item
    new_tenant = Tenant.load({
        'id': {
            'cloud': 'us-west1',
            'id': 'ed388ba9-dea3-4017-987b-92f7915f33bb',
            'type': 'example.Tenant'
        },
        'name': 'foobar'
    })
    with model.Transaction() as tx:
        tx.store(new_tenant)

    # Retrieving previously stored item
    with model.Transaction() as tx:
        object_id = model.ObjectId('ed388ba9-dea3-4017-987b-92f7915f33bb',
                                   'us-west1')
        stored_tenant = tx.retrieve(Tenant, object_id)
        assert stored_tenant.name == 'foobar'

    # Getting list of items
    with model.Transaction() as tx:
        found_tenant = None
        for tenant in tx.list(Tenant):
            if tenant.id == object_id:
                found_tenant = tenant
        assert found_tenant is not None
        assert found_tenant.name == 'foobar'


"""
import collections
import json
import sqlite3
import threading

import marshmallow
from marshmallow import fields

CREATE_OBJECT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS objects (
    uuid TEXT,
    cloud TEXT,
    type TEXT,
    json TEXT,
    PRIMARY KEY (uuid, cloud, type)
)
"""

ObjectId = collections.namedtuple('ObjectId', ('id', 'cloud'))
registry = {}


class DataAdapter(object):
    """
    Data adapter class that make possible passing non-dict objects to
    Schema.load. Not for use outside of ``Model.load_from_cloud`` code.
    """

    def __init__(self, obj, field_mapping, transformers):
        self.obj = obj
        self.field_mapping = field_mapping
        self.transformers = transformers
        self.override = {}

    def get(self, key, default):
        if key in self.override:
            return self.override[key]
        mapped_key = self.field_mapping.get(key, key)
        if isinstance(self.obj, dict):
            value = self.obj.get(mapped_key, default)
        else:
            value = getattr(self.obj, mapped_key, default)
        transformer = self.transformers.get(key)
        if transformer is not None:
            return transformer(value)
        else:
            return value

    def set(self, key, value):
        self.override[key] = value


class NotFound(Exception):
    """
    NotFound exception is thrown when object not found in database.
    """
    def __init__(self, cls, object_id):
        super(NotFound, self).__init__()
        self.cls = cls
        self.object_id = object_id

    def __str__(self):
        return '{0} object with id {1} not found.'.format(
            _type_name(self.cls), self.object_id)


class Schema(marshmallow.Schema):
    """
    Inherit this class to define object schema.
    """

    FIELD_MAPPING = {}
    FIELD_VALUE_TRANSFORMERS = {}

    def get_primary_key_field(self):
        for name, field in self.declared_fields.items():
            if isinstance(field, PrimaryKey):
                return name
        return None


class ModelMetaclass(type):
    def __new__(mcs, name, parents, dct):
        result = super(ModelMetaclass, mcs).__new__(mcs, name, parents, dct)
        if parents != (object,):
            result.pk_field = result.get_schema().get_primary_key_field()
        return result


class Model(object):
    """
    Inherit this class to define model class for OpenStack objects like
    tenants, volumes, servers, etc...
    Inherited classes must define ``Schema`` class inherited from
    ``model.Schema`` as member.
    If model is to be used as root object saved to database (e.g. not nested),
    then schema must include ``model.PrimaryKey`` field.
    """

    __metaclass__ = ModelMetaclass
    Schema = Schema
    pk_field = None

    def __init__(self):
        self._original = {}

    def dump(self):
        return self.get_schema().dump(self).data

    @classmethod
    def create(cls, values, schema=None, mark_dirty=False):
        """
        Create model instance using values from ``values`` argument without
        validation. To create model class instances previously validating
        input, ``Model.load`` or ``Model.load_from_cloud`` classmethods should
        be used.

        :param values: dictionary containing field values
        :param schema: schema instance
        :param mark_dirty: mark object as dirty (e.g. it will be stored to
                           database when transaction completes)
        :return: instance of model class
        """

        if schema is None:
            schema = cls.get_schema()
        obj = cls()
        for name, field in schema.fields.items():
            if isinstance(field, Nested):
                value = values.get(name)
                model = field.nested_model
                nested_schema = model.get_schema()
                nested_schema.context = schema.context
                if value is not None:
                    if field.many:
                        value = [model.create(x, nested_schema, mark_dirty)
                                 for x in value]
                    else:
                        value = model.create(value, nested_schema, mark_dirty)
                setattr(obj, name, value)
            else:
                value = values.get(name)
                if not mark_dirty:
                    if isinstance(field, Reference):
                        obj._original[name] = \
                            field.get_significant_value(value)
                    else:
                        obj._original[name] = value
                setattr(obj, name, value)
        return obj

    @classmethod
    def load_from_cloud(cls, cloud, data):
        """
        Create model class instance using data from cloud with validation.
        :param cloud: ``context.Cloud`` object
        :param data: dictionary or object returned by OpenStack API client
        :return: model class instance
        """

        def convert(field, many, old_value):
            if old_value is None:
                return None
            if many:
                convert_result = []
                for element in old_value:
                    converted = convert(field, False, element)
                    if converted is None:
                        continue
                    convert_result.append(converted)
                return convert_result
            else:
                object_id = _convert_object_id(cloud, old_value)
                if not field.ensure_existence or _ensure_existence(
                        cloud, field.model_class, object_id):
                    return object_id
                else:
                    return None

        def process_fields(schema, raw_data):
            if raw_data is None:
                return None
            adapted_data = DataAdapter(raw_data, schema.FIELD_MAPPING,
                                       schema.FIELD_VALUE_TRANSFORMERS)
            for name, field in schema.fields.items():
                key = field.load_from or name
                value = adapted_data.get(key, None)
                if value is None:
                    continue
                elif isinstance(field, Reference):
                    new_value = convert(field, field.many, value)
                    adapted_data.set(key, new_value)
                elif isinstance(field, Nested):
                    nested_schema = field.nested_model.get_schema()
                    nested_schema.context = schema.context
                    if field.many:
                        adapted_data.set(
                            key, [process_fields(nested_schema, x)
                                  for x in value])
                    else:
                        adapted_data.set(
                            key, process_fields(nested_schema, value))
            return adapted_data

        schema = cls.get_schema()
        schema.context = {'cloud': cloud}
        data = process_fields(schema, data)
        loaded, _ = schema.load(data)
        return cls.create(loaded, schema=schema, mark_dirty=True)

    @classmethod
    def load(cls, data):
        """
        Create model class instance with validation.
        :param data: dictionary containing model field data.
        :return: model class instance
        """
        schema = cls.get_schema()
        loaded, _ = schema.load(data)
        return cls.create(loaded, schema=schema, mark_dirty=False)

    @classmethod
    def get_schema(cls):
        """
        Returns model schema instance
        """
        return cls.Schema(strict=True)

    @property
    def primary_key(self):
        """
        Returns name of primary key field if it exists, None otherwise.
        """
        if self.pk_field is not None:
            return getattr(self, self.pk_field)
        else:
            return None

    @classmethod
    def load_missing(cls, cloud, object_id):
        """
        Method called by ``Model.load_from_cloud`` when it can't find
        dependency in the database to try to load dependency from cloud.

        :param cloud: cloud object that can be used to create OpenStack API
                      clients, etc...
        :param object_id: identifier of missing object
        :return: model class instance
        """
        raise NotFound(cls, object_id)

    @classmethod
    def discover(cls, cloud):
        """
        Method is called to discover and save to database all objects defined
        by model from cloud.
        :param cloud: cloud object that can be used to create OpenStack API
                      clients, etc...
        :return: model class instance
        """
        return

    def is_dirty(self):
        """
        Returns True if object have changed since load from database, False
        otherwise.
        """
        original = self._original
        schema = self.get_schema()
        for name, field in schema.declared_fields.items():
            value = getattr(self, name)
            if isinstance(field, Reference):
                if original.get(name) != field.get_significant_value(value):
                    return True
            elif isinstance(field, Nested):
                if field.many:
                    if any(x.is_dirty() for x in value):
                        return True
                else:
                    if value.is_dirty():
                        return True
            elif value != original.get(name):
                return True
        return False

    def mark_dirty(self):
        """
        Mark object as dirty e.g. it will be unconditionally saved to database
        when transaction completes.
        """
        self._original.clear()


class Reference(fields.Field):
    """
    Field referencing one or more model instances.
    """

    def __init__(self, model_class, many=False, ensure_existence=False,
                 **kwargs):
        super(Reference, self).__init__(**kwargs)
        self.model_class = model_class
        self.many = many
        self.ensure_existence = ensure_existence

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        model = self.model_class
        pk_field = model.pk_field
        if self.many:
            return [_object_id_to_dict(model, getattr(x, pk_field))
                    for x in value]
        else:
            return _object_id_to_dict(model, getattr(value, pk_field))

    def _deserialize(self, value, attr, data):
        if self.many:
            return [LazyObj(self.model_class, _to_object_id(x))
                    for x in value]
        else:
            return LazyObj(self.model_class, _to_object_id(value))

    def get_significant_value(self, value):
        if value is None:
            return None
        model = self.model_class
        pk_field = model.pk_field
        if self.many:
            return set(getattr(x, pk_field) for x in value)
        else:
            return getattr(value, pk_field)


class Dependency(Reference):
    """
    Dependency field is the same as reference except that it show that object
    can't exist without the dependency.
    """

    def __init__(self, model_class, many=False, **kwargs):
        super(Dependency, self).__init__(
            model_class, many=many, ensure_existence=True, **kwargs)


class Nested(fields.Nested):
    """
    Nested model field.
    """

    def __init__(self, nested_model, **kwargs):
        super(Nested, self).__init__(nested_model.Schema, **kwargs)
        self.nested_model = nested_model


class PrimaryKey(fields.Field):
    """
    Primary key field. Root objects (non nested) should have one primary key
    field.
    """

    def __init__(self, real_name=None, **kwargs):
        super(PrimaryKey, self).__init__(
            load_from=real_name, dump_to=real_name, required=True, **kwargs)

    def _serialize(self, value, attr, obj):
        return _object_id_to_dict(_get_class(obj), value)

    def _deserialize(self, value, attr, data):
        cloud = self.context.get('cloud')
        if cloud is not None:
            value = _convert_object_id(cloud, value)
        return _to_object_id(value)


class LazyObj(object):
    """
    Lazy loaded object. Used internally to prevent loading whole database
    through dependencies/references.
    """

    def __init__(self, cls, object_id):
        self._model = cls
        self._object_id = object_id
        self._object = None

    def __getattr__(self, name):
        if name == self._model.pk_field:
            return self._object_id
        self._retrieve_obj()
        return getattr(self._object, name)

    def __repr__(self):
        if self._object is not None:
            return repr(self._object)
        else:
            cls = self.__class__
            return '<{module}.{cls} {uuid}>'.format(
                module=cls.__module__, cls=cls.__name__, uuid=self._object_id)

    def _retrieve_obj(self):
        if self._object is None:
            with Transaction() as tx:
                self._object = tx.retrieve(self._model, self._object_id)


class Transaction(object):
    """
    Transaction objects are used to store and retrieve objects to database. It
    tracks already loaded object to prevent loading same object twice and
    to prevent losing changes made to already loaded objects.
    Transactions should be used as context managers (e.g. inside ``with``
    block). On exit from this block all changes made using transaction will
    be saved to disk.
    """

    tls = threading.local()
    tls.current = None

    def __init__(self):
        self.session = None
        self.connection = None
        self.cursor = None

    def __enter__(self):
        if self.tls.current is not None:
            # TODO: use save points for nested transactions
            current_tx = self.tls.current
            self.connection = current_tx.connection
            self.cursor = current_tx.cursor
            self.session = current_tx.session
            return self
        filepath = 'migration_data.db'
        self.connection = sqlite3.connect(filepath)
        self.connection.isolation_level = None
        self.cursor = self.connection.cursor()
        self.cursor.execute('BEGIN')
        self.cursor.execute(CREATE_OBJECT_TABLE_SQL)
        self.tls.current = self
        self.session = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tls.current is not self:
            # TODO: use save points for nested transactions
            return

        self.tls.current = None
        if exc_type is not None or exc_val is not None or exc_tb is not None:
            self.cursor.execute('ROLLBACK')
            return
        try:
            for obj in self.session.values():
                if obj.is_dirty():
                    self._update_row(obj)
            self.cursor.execute('COMMIT')
        except Exception:
            self.cursor.execute('ROLLBACK')
            raise
        finally:
            self.cursor.close()
            self.connection.close()

    def store(self, obj):
        """
        Stores object to database. Object model schema should have PrimaryKey
        field.
        :param obj: model instance
        """
        pk = obj.primary_key
        if pk is None:
            raise TypeError('Can\'t store object without PrimaryKey field.')
        key = (_get_class(obj), pk)
        self.session[key] = obj

    def retrieve(self, cls, object_id):
        """
        Loads object from database using class and object_id. If no such object
        were found, this method will throw ``model.NotFound`` exception.
        :param cls: model class
        :param object_id: model.ObjectId instance
        :return: model instance
        """

        key = (cls, object_id)
        if key in self.session:
            return self.session[key]
        self.cursor.execute('SELECT json FROM objects WHERE uuid=? AND '
                            'cloud=? AND type=?',
                            (object_id.id, object_id.cloud, _type_name(cls)))
        result = self.cursor.fetchone()
        if not result or not result[0]:
            raise NotFound(cls, object_id)
        obj = cls.load(json.loads(result[0]))
        self.session[key] = obj
        return obj

    def list(self, cls, cloud=None):
        """
        Returns list of all objects of class ``cls`` stored in the database. If
        cloud argument is not None, then list is filtered by cloud.
        :param cls: model class
        :param cloud: cloud name or None
        :return: list of model instances
        """
        if cloud is None:
            self.cursor.execute('SELECT uuid, cloud, json '
                                'FROM objects WHERE type=?',
                                (_type_name(cls),))
        else:
            self.cursor.execute('SELECT uuid, cloud, json '
                                'FROM objects WHERE cloud=? AND type=?',
                                (cloud, _type_name(cls)))
        result = []
        for obj in self.session.values():
            if isinstance(obj, cls) and \
                    (cloud is None or cloud == obj.primary_key.cloud):
                result.append(obj)

        for row in self.cursor.fetchall():
            uuid, cloud, json_data = row
            key = (cls, ObjectId(uuid, cloud))
            if key in self.session or not json_data:
                continue
            obj = cls.load(json.loads(json_data))
            self.session[key] = obj
            result.append(obj)
        return result

    def _update_row(self, obj):
        pk = obj.primary_key
        uuid = pk.id
        cloud = pk.cloud
        type_name = _type_name(_get_class(obj))
        self.cursor.execute('INSERT OR REPLACE INTO objects '
                            'VALUES (?, ?, ?, ?)',
                            (uuid, cloud, type_name, json.dumps(obj.dump())))


def _type_name(cls):
    return cls.__module__ + '.' + cls.__name__


def _get_class(obj):
    if isinstance(obj, LazyObj):
        return obj._model
    else:
        return obj.__class__


def _convert_object_id(cloud, value):
    if isinstance(value, basestring):
        return ObjectId(value, cloud.name)
    elif isinstance(value, dict) and 'id' in value:
        return ObjectId(value['id'], cloud.name)
    else:
        raise ValueError('Can\'t convert ' + repr(value) + ' to ObjectId')


def _ensure_existence(cloud, cls, object_id):
    with Transaction() as tx:
        try:
            tx.retrieve(cls, object_id)
            return True
        except NotFound:
            obj = cls.load_missing(cloud, object_id)
            if obj is None:
                return False
            tx.store(obj)
            return True


def _to_object_id(value):
    if isinstance(value, dict):
        return ObjectId(value['id'], value['cloud'])
    elif isinstance(value, ObjectId):
        return value
    else:
        raise ValueError('Can\'t convert ' + repr(value) + ' to ObjectId')


def _object_id_to_dict(cls, object_id):
    return {
        'id': object_id.id,
        'cloud': object_id.cloud,
        'type': _type_name(cls)
    }
