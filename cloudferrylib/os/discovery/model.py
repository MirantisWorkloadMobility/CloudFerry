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
            with model.Session() as session:
                for raw_volume in volumes_list:
                    volume = Volume.load_from_cloud(cloud, raw_volume)
                    session.store(volume)


Example using ``Session`` class to store and retrieve data from database::

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
    with model.Session() as session:
        session.store(new_tenant)

    # Retrieving previously stored item
    with model.Session() as session:
        object_id = model.ObjectId('ed388ba9-dea3-4017-987b-92f7915f33bb',
                                   'us-west1')
        stored_tenant = session.retrieve(Tenant, object_id)
        assert stored_tenant.name == 'foobar'

    # Getting list of items
    with model.Session() as session:
        found_tenant = None
        for tenant in session.list(Tenant):
            if tenant.id == object_id:
                found_tenant = tenant
        assert found_tenant is not None
        assert found_tenant.name == 'foobar'


"""
import collections
import contextlib
import json
import logging
import sys
import threading

import marshmallow
from marshmallow import fields
from oslo_utils import importutils

from cloudferrylib.utils import local_db

LOG = logging.getLogger(__name__)
type_aliases = {}
local_db.execute_once("""
CREATE TABLE IF NOT EXISTS objects (
    uuid TEXT,
    cloud TEXT,
    type TEXT,
    json TEXT,
    PRIMARY KEY (uuid, cloud, type)
)
""")


class ObjectId(collections.namedtuple('ObjectId', ('id', 'cloud'))):
    """
    Object identifier class containing the identifier itself and cloud name
    as specified in discover.yaml
    """

    @staticmethod
    def from_cloud(cloud, value):
        """
        Create ObjectId based on cloud name and identifier string (used mostly
        during discover phase).
        """
        if isinstance(value, basestring):
            return ObjectId(value, cloud.name)
        elif isinstance(value, dict) and 'id' in value:
            return ObjectId(value['id'], cloud.name)
        else:
            raise ValueError('Can\'t convert ' + repr(value) + ' to ObjectId')

    @staticmethod
    def convert(value):
        """
        Deserialize ObjectId from dictionary representation.
        """
        if isinstance(value, dict):
            return ObjectId(value['id'], value['cloud'])
        elif isinstance(value, ObjectId):
            return value
        else:
            raise ValueError('Can\'t convert ' + repr(value) + ' to ObjectId')

    def to_dict(self, cls):
        """
        Serialize ObjectId to dictionary representation.
        """
        return {
            'id': self.id,
            'cloud': self.cloud,
            'type': _type_name(cls),
        }


class DataAdapter(object):
    """
    Data adapter class that make possible passing non-dict objects to
    Schema.load. Not for use outside of ``Model.load_from_cloud`` code.
    """

    def __init__(self, obj, field_mapping, transformers, overrides=None):
        self.obj = obj
        self.field_mapping = field_mapping
        self.transformers = transformers
        self.override = overrides or {}

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
        # pylint: disable=protected-access

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
    def load_from_cloud(cls, cloud, data, overrides=None):
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
                object_id = ObjectId.from_cloud(cloud, old_value)
                if not field.ensure_existence or \
                        field.model_class.find(cloud, object_id):
                    return object_id
                else:
                    return None

        def process_fields(schema, raw_data, overrides=None):
            if raw_data is None:
                return None
            adapted_data = DataAdapter(raw_data, schema.FIELD_MAPPING,
                                       schema.FIELD_VALUE_TRANSFORMERS,
                                       overrides)
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
        data = process_fields(schema, data, overrides)
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
        # pylint: disable=unused-argument
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
        # pylint: disable=unused-argument
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

    def clear_dirty(self):
        """
        Update internal state of object so it's not considered dirty (e.g.
        don't need to be saved to database).
        """
        schema = self.get_schema()
        for name, field in schema.fields.items():
            if isinstance(field, Nested):
                value = getattr(self, name, None)
                if value is not None:
                    if field.many:
                        for elem in value:
                            elem.clear_dirty()
                    else:
                        value.clear_dirty()
            else:
                value = getattr(self, name, None)
                if isinstance(field, Reference):
                    self._original[name] = \
                        field.get_significant_value(value)
                else:
                    self._original[name] = value

    def dependencies(self):
        """
        Return list of other model instances that current object depend upon.
        """
        result = []
        schema = self.get_schema()
        for name, field in schema.declared_fields.items():
            if isinstance(field, Dependency):
                result.append(getattr(self, name))
        return result

    @classmethod
    def find(cls, cloud, object_id):
        """
        Try to find object in DB, and if it's missing in DB try to fetch it
        from cloud. Should be used during discover phase only.
        :param cloud: cloud object that can be used to create OpenStack API
                      clients, etc...
        :param object_id: object identifier
        :return object or None if it's missing even in cloud
        """
        with Session.current() as session:
            try:
                if session.is_missing(cls, object_id):
                    return None
                else:
                    return session.retrieve(cls, object_id)
            except NotFound:
                LOG.debug('Trying to load missing %s value: %s',
                          _type_name(cls), object_id)
                obj = cls.load_missing(cloud, object_id)
                if obj is None:
                    session.store_missing(cls, object_id)
                    return None
                else:
                    session.store(obj)
                    return obj

    @classmethod
    def get_class(cls):
        """
        Returns model class.
        """
        return cls

    def get(self, name, default=None):
        """
        Returns object attribute by name.
        """
        return getattr(self, name, default)

    def __repr__(self):
        schema = self.get_schema()
        obj_fields = sorted(schema.declared_fields.keys())
        cls = self.__class__
        return '<{cls} {fields}>'.format(
            cls=_type_name(cls),
            fields=' '.join('{0}:{1}'.format(f, getattr(self, f))
                            for f in obj_fields))


class Reference(fields.Field):
    """
    Field referencing one or more model instances.
    """

    def __init__(self, model_class, many=False, ensure_existence=False,
                 **kwargs):
        super(Reference, self).__init__(**kwargs)
        if isinstance(model_class, basestring):
            self._model_class_name = model_class
            self._model_class = None
        else:
            self._model_class = model_class
        self.many = many
        self.ensure_existence = ensure_existence

    @property
    def model_class(self):
        if self._model_class is None:
            self._model_class = importutils.import_class(
                self._model_class_name)
        return self._model_class

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        model = self.model_class
        pk_field = model.pk_field
        if self.many:
            return [getattr(x, pk_field).to_dict(model)
                    for x in value]
        else:
            return getattr(value, pk_field).to_dict(model)

    def _deserialize(self, value, attr, data):
        if self.many:
            return [LazyObj(self.model_class, ObjectId.convert(x))
                    for x in value]
        else:
            return LazyObj(self.model_class, ObjectId.convert(value))

    def get_significant_value(self, value):
        """
        Returns id or set of id that can be safely used for detection of
        changes to the field. E.g. don't compare previous and current objects
        that are referenced, only compare id/set of ids.
        """
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
        return value.to_dict(obj.get_class())

    def _deserialize(self, value, attr, data):
        cloud = self.context.get('cloud')
        if cloud is not None:
            value = ObjectId.from_cloud(cloud, value)
        return ObjectId.convert(value)


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
            with Session.current() as session:
                self._object = session.retrieve(self._model, self._object_id)

    def get(self, name):
        """
        Returns object attribute by name.
        """
        return getattr(self, name, None)

    def get_class(self):
        """
        Return model class.
        """
        return self._model


class Session(object):
    """
    Session objects are used to store and retrieve objects to database. It
    tracks already loaded object to prevent loading same object twice and
    to prevent losing changes made to already loaded objects.
    Sessions should be used as context managers (e.g. inside ``with``
    block). On exit from this block all changes made using session will
    be saved to disk.
    """

    _tls = threading.local()
    _tls.current = None

    def __init__(self):
        self.session = None
        self.previous = None
        self.tx = None

    def __enter__(self):
        # pylint: disable=protected-access
        self.previous = self._tls.current
        self._tls.current = self
        if self.previous is not None:
            # Store outer TX values for savepoint
            self.previous._dump_objects()
        self.tx = local_db.Transaction()
        self.tx.__enter__()
        self.session = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._tls.current = self.previous
        try:
            if exc_type is None and exc_val is None and exc_tb is None:
                self._dump_objects()
        except Exception:
            LOG.error('Exception dumping objects', exc_info=True)
            exc_type, exc_val, exc_tb = sys.exc_info()
            raise
        finally:
            self.tx.__exit__(exc_type, exc_val, exc_tb)

    def _dump_objects(self):
        for (cls, pk), obj in self.session.items():
            if obj is None:
                self._store_none(cls, pk)
                continue
            if obj.is_dirty():
                self._update_row(obj)

    @classmethod
    def current(cls):
        """
        Returns current session or create new session if there is no session
        started yet.
        :return: Session instance
        """
        current = cls._tls.current
        if current is not None:
            @contextlib.contextmanager
            def noop_ctx_mgr():
                yield current
            return noop_ctx_mgr()
        else:
            return Session()

    def store(self, obj):
        """
        Stores object to database. Object model schema should have PrimaryKey
        field.
        :param obj: model instance
        """
        pk = obj.primary_key
        if pk is None:
            raise TypeError('Can\'t store object without PrimaryKey field.')
        LOG.debug('Storing: %s', obj)
        key = (obj.get_class(), pk)
        self.session[key] = obj

    def store_missing(self, cls, object_id):
        """
        Stores information that object is missing in cloud
        :param object_id: model.ObjectId instance
        """
        LOG.debug('Storing missing: %s %s', _type_name(cls), object_id)
        key = (cls, object_id)
        self.session[key] = None

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
        result = self.tx.query_one('SELECT json FROM objects WHERE uuid=:uuid '
                                   'AND cloud=:cloud AND type=:type_name',
                                   uuid=object_id.id,
                                   cloud=object_id.cloud,
                                   type_name=_type_name(cls))
        if not result or not result[0]:
            raise NotFound(cls, object_id)
        obj = cls.load(json.loads(result[0]))
        self.session[key] = obj
        return obj

    def is_missing(self, cls, object_id):
        """
        Check if object couldn't be found in cloud (e.g. was deleted)
        :param cls: model class
        :param object_id: model.ObjectId instance
        :return:
        """
        key = (cls, object_id)
        if key in self.session:
            return self.session[key] is None
        result = self.tx.query_one('SELECT json FROM objects WHERE uuid=:uuid '
                                   'AND cloud=:cloud AND type=:type_name',
                                   uuid=object_id.id,
                                   cloud=object_id.cloud,
                                   type_name=_type_name(cls))
        if not result:
            raise NotFound(cls, object_id)
        return result[0] is None

    def list(self, cls, cloud=None):
        """
        Returns list of all objects of class ``cls`` stored in the database. If
        cloud argument is not None, then list is filtered by cloud.
        :param cls: model class
        :param cloud: cloud name or None
        :return: list of model instances
        """
        if cloud is None:
            query = 'SELECT uuid, cloud, json ' \
                    'FROM objects WHERE type=:type_name'
        else:
            query = 'SELECT uuid, cloud, json ' \
                    'FROM objects WHERE cloud=:cloud AND type=:type_name'
        result = []
        for obj in self.session.values():
            if isinstance(obj, cls) and \
                    (cloud is None or cloud == obj.primary_key.cloud):
                result.append(obj)

        for row in self.tx.query(query, type_name=_type_name(cls),
                                 cloud=cloud):
            uuid, cloud, json_data = row
            key = (cls, ObjectId(uuid, cloud))
            if key in self.session or not json_data:
                continue
            obj = cls.load(json.loads(json_data))
            self.session[key] = obj
            result.append(obj)
        return result

    def delete(self, cls=None, cloud=None, object_id=None):
        """
        Deletes all objects that have cls or cloud or object_id that are equal
        to values passed as arguments. Arguments that are None are ignored.
        """
        if cloud is not None and object_id is not None:
            assert object_id.cloud == cloud
        for key in self.session.keys():
            obj_cls, obj_pk = key
            matched = True
            if cls is not None and cls is not obj_cls:
                matched = False
            if cloud is not None and obj_pk.cloud != cloud:
                matched = False
            if object_id is not None and object_id != obj_pk:
                matched = False
            if matched:
                del self.session[key]
        self._delete_rows(cls, cloud, object_id)

    def _update_row(self, obj):
        pk = obj.primary_key
        uuid = pk.id
        cloud = pk.cloud
        type_name = _type_name(obj.get_class())
        self.tx.execute('INSERT OR REPLACE INTO objects '
                        'VALUES (:uuid, :cloud, :type_name, :data)',
                        uuid=uuid, cloud=cloud, type_name=type_name,
                        data=json.dumps(obj.dump()))
        obj.clear_dirty()
        assert not obj.is_dirty()

    def _store_none(self, cls, pk):
        uuid = pk.id
        cloud = pk.cloud
        type_name = _type_name(cls)
        self.tx.execute('INSERT OR REPLACE INTO objects '
                        'VALUES (:uuid, :cloud, :type_name, NULL)',
                        uuid=uuid, cloud=cloud, type_name=type_name)

    def _delete_rows(self, cls, cloud, object_id):
        predicates = []
        kwargs = {}
        if cls is not None:
            predicates.append('type=:type_name')
            kwargs['type_name'] = _type_name(cls)
        if object_id is not None:
            predicates.append('uuid=:uuid')
            kwargs['uuid'] = object_id.id
            if cloud is None:
                cloud = object_id.cloud
            else:
                assert cloud == object_id.cloud
        if cloud is not None:
            predicates.append('cloud=:cloud')
            kwargs['cloud'] = cloud
        statement = 'DELETE FROM objects WHERE'
        if predicates:
            statement += ' AND '.join(predicates)
        else:
            statement += ' 1'
        self.tx.execute(statement, **kwargs)


def type_alias(name):
    """
    Decorator function that add alias for some model class
    :param name: alias name
    """

    def wrapper(cls):
        assert issubclass(cls, Model)
        type_aliases[name] = cls
        return cls
    return wrapper


def get_model(type_name):
    """
    Return model class instance using either alias or fully qualified name.
    :param type_name: alias or fully qualified class name
    :return: subclass of Model
    """
    if type_name in type_aliases:
        return type_aliases[type_name]
    else:
        return importutils.import_class(type_name)


def _type_name(cls):
    return cls.__module__ + '.' + cls.__name__
