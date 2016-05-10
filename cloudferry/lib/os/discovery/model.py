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
    from cloudferry.lib.os.discovery import model
    from cloudferry.lib.os.discovery import nova


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
            volume_client = clients.volume_client(cloud)
            raw_volume = volume_client.volumes.get(object_id.id)
            return Volume.load_from_cloud(cloud, raw_volume)

        @classmethod
        def discover(cls, cloud):
            volume_client = clients.volume_client(cloud)
            volumes_list = volume_client.volumes.list(
                search_opts={'all_tenants': True})
            with model.Session() as session:
                for raw_volume in volumes_list:
                    volume = Volume.load_from_cloud(cloud, raw_volume)
                    session.store(volume)


Example using ``Session`` class to store and retrieve data from database::

    from cloudferry.lib.os.discovery import model


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
import logging
import sys

import marshmallow
from marshmallow import exceptions
from marshmallow import fields
from oslo_utils import importutils

from cloudferry.lib.utils import local_db
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)
type_aliases = {}
local_db.execute_once("""
CREATE TABLE IF NOT EXISTS objects (
    uuid TEXT,
    cloud TEXT,
    type TEXT,
    json JSON,
    PRIMARY KEY (uuid, cloud, type)
)
""")
local_db.execute_once("""
CREATE TABLE IF NOT EXISTS links (
    uuid TEXT,
    cloud TEXT,
    type TEXT,
    json JSON,
    PRIMARY KEY (uuid, cloud, type)
)
""")
ValidationError = exceptions.ValidationError


class ObjectId(collections.namedtuple('ObjectId', ('id', 'cloud'))):
    """
    Object identifier class containing the identifier itself and cloud name
    as specified in discover.yaml
    """

    @staticmethod
    def from_cloud(cloud, value, model):
        """
        Create ObjectId based on cloud name and identifier string (used mostly
        during discover phase).
        """
        if isinstance(value, basestring):
            uuid = value
        elif isinstance(value, dict) and 'id' in value:
            uuid = value['id']
        else:
            raise ValueError('Can\'t convert ' + repr(value) + ' to ObjectId')
        return {
            'id': uuid,
            'cloud': cloud.name,
            'type': utils.qualname(model),
        }

    @staticmethod
    def from_dict(value):
        """
        Deserialize ObjectId from dictionary representation.
        """
        if isinstance(value, dict):
            return ObjectId(value['id'], value['cloud'])
        else:
            raise ValueError('Can\'t convert ' + repr(value) + ' to ObjectId')

    def to_dict(self, cls):
        """
        Serialize ObjectId to dictionary representation.
        """
        return {
            'id': self.id,
            'cloud': self.cloud,
            'type': utils.qualname(cls),
        }


class DataAdapter(object):
    """
    Data adapter class that make possible passing non-dict objects to
    Schema.load. Not for use outside of ``Model.load_from_cloud`` code.
    """
    missing = object()

    def __init__(self, obj, field_mapping, transformers, overrides=None):
        self.obj = obj
        self.field_mapping = field_mapping
        self.transformers = transformers
        self.override = overrides or {}

    def get(self, key, default):
        if key in self.override:
            value = self.override[key]
            if value is self.missing:
                return default
            else:
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

    def set_missing(self, key):
        self.override[key] = self.missing


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
            utils.qualname(self.cls), self.object_id)


class _FieldWithTable(object):
    def __init__(self, *args, **kwargs):
        self.table = kwargs.pop('table', 'objects')
        super(_FieldWithTable, self).__init__(*args, **kwargs)


class String(_FieldWithTable, fields.String):
    pass


class Boolean(_FieldWithTable, fields.Boolean):
    pass


class Integer(_FieldWithTable, fields.Integer):
    pass


class Dict(_FieldWithTable, fields.Dict):
    pass


class Reference(_FieldWithTable, fields.Field):
    """
    Field referencing one or more model instances.
    """

    def __init__(self, model_class, many=False, ensure_existence=False,
                 convertible=True, **kwargs):
        super(Reference, self).__init__(**kwargs)
        if isinstance(model_class, basestring):
            self._model_class_name = model_class
            self._model_class = None
        else:
            self._model_class = model_class
        self.many = many
        self.ensure_existence = ensure_existence
        self.convertible = convertible
        # TODO: validation

    @property
    def model_class(self):
        if self._model_class is None:
            self._model_class = get_model(self._model_class_name)
        return self._model_class

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        if self.many:
            return [x.primary_key.to_dict(x.get_class())
                    for x in value]
        else:
            return value.primary_key.to_dict(value.get_class())

    def _deserialize(self, value, attr, data):
        with Session.current() as session:
            if self.many:
                result = []
                for obj in value:
                    model = get_model(obj['type'])
                    object_id = ObjectId.from_dict(obj)
                    if not self.ensure_existence or \
                            session.exists(model, object_id):
                        result.append(LazyObj(model, object_id))
                return result
            else:
                model = get_model(value['type'])
                object_id = ObjectId.from_dict(value)
                if not self.ensure_existence or \
                        session.exists(model, object_id):
                    return LazyObj(model, object_id)
                else:
                    return None

    def get_significant_value(self, value):
        """
        Returns id or set of id that can be safely used for detection of
        changes to the field. E.g. don't compare previous and current objects
        that are referenced, only compare id/set of ids.
        """
        if value is None:
            return None
        if self.many:
            return set(x.primary_key for x in value)
        else:
            return value.primary_key


class ModelMetaclass(type):
    def __new__(mcs, name, parents, dct):
        result = super(ModelMetaclass, mcs).__new__(mcs, name, parents, dct)
        if dct['Schema'] is not None:
            result.pk_field = result.get_schema().get_primary_key_field()
        return result


class _EqualityByPrimaryKeyMixin(object):
    def __eq__(self, other):
        if other is None:
            return False
        self_pk = self.primary_key
        other_pk = other.primary_key
        if self_pk is None and other_pk is None:
            return id(self) == id(other)
        else:
            return self_pk == other_pk

    def __ne__(self, other):
        return not self.__eq__(other)


class Model(_EqualityByPrimaryKeyMixin):
    """
    Inherit this class to define model class for OpenStack objects like
    tenants, volumes, servers, etc...
    Inherited classes must define ``Schema`` class inherited from
    ``model.Schema`` as member.
    If model is to be used as root object saved to database (e.g. not nested),
    then schema must include ``model.PrimaryKey`` field.
    """

    __metaclass__ = ModelMetaclass
    Schema = None
    pk_field = None

    def __init__(self):
        self._original = {}

    def dump(self, table=None):
        return self.get_schema(table).dump(self).data

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

        def find_object(object_id_dict):
            model = get_model(object_id_dict['type'])
            object_id = ObjectId.from_dict(object_id_dict)
            with Session.current() as session:
                try:
                    if session.is_missing(model, object_id):
                        return None
                    else:
                        return session.retrieve(model, object_id)
                except NotFound:
                    LOG.debug('Trying to load missing %s value: %s',
                              utils.qualname(model), object_id)
                    obj = model.load_missing(cloud, object_id)
                    if obj is None:
                        session.store_missing(model, object_id)
                        return None
                    else:
                        session.store(obj)
                        return obj

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
                model = field.model_class
                object_id_dict = ObjectId.from_cloud(cloud, old_value, model)
                if not field.ensure_existence or find_object(object_id_dict):
                    return object_id_dict
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
                    if not field.convertible:
                        adapted_data.set_missing(key)
                        continue
                    new_value = convert(field, field.many, value)
                    adapted_data.set(key, new_value)
                elif isinstance(field, PrimaryKey):
                    adapted_data.set(
                        key, ObjectId.from_cloud(cloud, value, cls))
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
        return cls.create(loaded, schema=schema, mark_dirty=True)

    @classmethod
    def get_schema(cls, table=None):
        """
        Returns model schema instance
        """
        # pylint: disable=not-callable
        schema = cls.Schema(strict=True)
        if table is not None:
            only = tuple(n for n, f in schema.fields.items()
                         if f.table == table)
            return cls.Schema(strict=True, only=only)
        else:
            return schema

    @property
    def primary_key(self):
        """
        Returns primary key value.
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

    def is_dirty(self, table):
        """
        Returns True if object have changed since load from database, False
        otherwise.
        """
        original = self._original
        schema = self.get_schema(table)
        for name, field in schema.fields.items():
            value = getattr(self, name)
            if isinstance(field, Reference):
                if original.get(name) != field.get_significant_value(value):
                    return True
            elif isinstance(field, Nested):
                if field.many:
                    if any(x.is_dirty(table) for x in value):
                        return True
                else:
                    if value.is_dirty(table):
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

    def clear_dirty(self, table):
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
                            elem.clear_dirty(table)
                    else:
                        value.clear_dirty(table)
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
        for name, field in schema.fields.items():
            if isinstance(field, Dependency):
                value = getattr(self, name)
                if field.many:
                    result.extend(value)
                elif value is not None:
                    result.append(value)
        return result

    @classmethod
    def get_class(cls):
        """
        Returns model class.
        """
        return cls

    @classmethod
    def get_class_qualname(cls):
        """
        Return fully qualified name of class (with module name, etc...)
        """
        return utils.qualname(cls)

    def get(self, name, default=None):
        """
        Returns object attribute by name.
        """
        return getattr(self, name, default)

    def equals(self, other):
        """
        Returns True if objects are same even if they are in different clouds.
        For example, same image that was manually uploaded to tenant with name
        "admin" to different clouds are equal, and therefore don't need to be
        migrated.
        """
        return self is other

    def link_to(self, dst_obj):
        """
        Link object to object in other cloud. Linked objects are incarnations
        of the same object in different clouds. E.g. when some object A is
        migrated to object B, then link from object A to object B is added.
        """
        # pylint: disable=no-member
        assert self.get_class() is dst_obj.get_class()
        assert self.primary_key is not None
        if dst_obj in self.links:
            return
        self.links.append(dst_obj)

    def find_link(self, cloud):
        """
        Find linked object in specified cloud.
        """
        # pylint: disable=no-member
        assert self.primary_key is not None
        for link in self.links:
            if link.primary_key.cloud == cloud:
                return link
        return None

    def get_uuid_in(self, cloud):
        """
        Find linked object in specified cloud and return it's UUID.
        """
        obj = self.find_link(cloud)
        assert obj is not None
        return obj.primary_key.id

    @classmethod
    def get_tables(cls):
        """
        Return list of tables for which fields was defined.
        """
        return set(f.table for f in cls.get_schema().fields.values())

    def __repr__(self):
        schema = self.get_schema()
        obj_fields = sorted(schema.fields.keys())
        cls = self.__class__
        return '<{cls} {fields}>'.format(
            cls=utils.qualname(cls),
            fields=' '.join('{0}:{1}'.format(f, getattr(self, f))
                            for f in obj_fields))


class Schema(marshmallow.Schema):
    """
    Inherit this class to define object schema.
    """
    links = Reference(Model, convertible=False, many=True, missing=list,
                      table='links')

    FIELD_MAPPING = {}
    FIELD_VALUE_TRANSFORMERS = {}

    def get_primary_key_field(self):
        for name, field in self.fields.items():
            if isinstance(field, PrimaryKey):
                return name
        return None


class Dependency(Reference):
    """
    Dependency field is the same as reference except that it show that object
    can't exist without the dependency.
    """

    def __init__(self, model_class, many=False, **kwargs):
        super(Dependency, self).__init__(
            model_class, many=many, ensure_existence=True, **kwargs)


class Nested(_FieldWithTable, fields.Nested):
    """
    Nested model field.
    """

    def __init__(self, nested_model, **kwargs):
        super(Nested, self).__init__(nested_model.Schema, **kwargs)
        self.nested_model = nested_model


class PrimaryKey(_FieldWithTable, fields.Field):
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
        return ObjectId.from_dict(value)


class LazyObj(_EqualityByPrimaryKeyMixin):
    """
    Lazy loaded object. Used internally to prevent loading whole database
    through dependencies/references.
    """

    def __init__(self, cls, object_id):
        self._model = cls
        self._object = None
        self.primary_key = object_id

    def is_dirty(self, table):
        """
        Returns True if object have changed since load from database, False
        otherwise.
        """
        if self._object is None:
            return False
        else:
            return self._object.is_dirty(table)

    def __getattr__(self, name):
        if name == self._model.pk_field:
            return self.primary_key
        self._retrieve_obj()
        return getattr(self._object, name)

    def __repr__(self):
        if self._object is not None:
            return repr(self._object)
        else:
            cls = self.__class__
            return '<{module}.{cls} {uuid}>'.format(
                module=cls.__module__, cls=cls.__name__, uuid=self.primary_key)

    def _retrieve_obj(self):
        if self._object is None:
            with Session.current() as session:
                self._object = session.retrieve(self._model, self.primary_key)

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

    def get_class_qualname(self):
        """
        Return fully qualified name of class (with module name, etc...)
        """
        return utils.qualname(self._model)


class Session(object):
    """
    Session objects are used to store and retrieve objects to database. It
    tracks already loaded object to prevent loading same object twice and
    to prevent losing changes made to already loaded objects.
    Sessions should be used as context managers (e.g. inside ``with``
    block). On exit from this block all changes made using session will
    be saved to disk.
    """

    _tls = utils.ThreadLocalStorage(current=None)

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
            for table in obj.get_tables():
                if obj.is_dirty(table):
                    self._update_row(obj, table)

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
        LOG.debug('Storing missing: %s %s', utils.qualname(cls), object_id)
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

        query = self._make_sql(cls, 'uuid', 'cloud', 'type')
        result = self.tx.query_one(query, uuid=object_id.id,
                                   cloud=object_id.cloud,
                                   type=utils.qualname(cls))
        if not result or not result[0]:
            raise NotFound(cls, object_id)
        schema = cls.get_schema()
        loaded, _ = schema.load(self._merge_obj(result))
        obj = cls.create(loaded, schema=schema, mark_dirty=False)
        self.session[key] = obj
        return obj

    def exists(self, cls, object_id):
        """
        Returns True if object exists in database, False otherwise
        :param cls: model class
        :param object_id: model.ObjectId instance
        :return: True or False
        """
        key = (cls, object_id)
        if key in self.session:
            return self.session[key] is not None
        result = self.tx.query_one('SELECT EXISTS(SELECT 1 FROM objects '
                                   'WHERE uuid=:uuid AND cloud=:cloud '
                                   'AND type=:type LIMIT 1)',
                                   uuid=object_id.id,
                                   cloud=object_id.cloud,
                                   type=utils.qualname(cls))
        return bool(result[0])

    def is_missing(self, cls, object_id):
        """
        Check if object couldn't be found in cloud (e.g. was deleted)
        :param cls: model class
        :param object_id: model.ObjectId instance
        :return: True or False
        """
        key = (cls, object_id)
        if key in self.session:
            return self.session[key] is None
        result = self.tx.query_one('SELECT json FROM objects WHERE uuid=:uuid '
                                   'AND cloud=:cloud AND type=:type_name',
                                   uuid=object_id.id,
                                   cloud=object_id.cloud,
                                   type_name=utils.qualname(cls))
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
            query = self._make_sql(cls, 'type', list=True)
        else:
            query = self._make_sql(cls, 'type', 'cloud', list=True)
        result = []
        for obj in self.session.values():
            if isinstance(obj, cls) and \
                    (cloud is None or cloud == obj.primary_key.cloud):
                result.append(obj)

        schema = cls.get_schema()
        for row in self.tx.query(query, type=utils.qualname(cls), cloud=cloud):
            uuid, cloud = row[:2]
            key = (cls, ObjectId(uuid, cloud))
            if key in self.session or not row[2]:
                continue
            loaded, _ = schema.load(self._merge_obj(row[2:]))
            obj = cls.create(loaded, schema=schema, mark_dirty=False)
            self.session[key] = obj
            result.append(obj)
        return result

    def delete(self, cls=None, cloud=None, object_id=None, table='objects'):
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
        self._delete_rows(cls, cloud, object_id, table)

    @staticmethod
    def _make_sql(model, *columns, **kwargs):
        is_list = kwargs.get('list', False)
        tables = model.get_tables()
        tables.remove('objects')

        query = 'SELECT '
        if is_list:
            query += 'objects.uuid, objects.cloud, '
        query += 'objects.json'
        for table in tables:
            query += ', {0}.json'.format(table)
        query += ' FROM objects '
        for table in tables:
            query += 'LEFT JOIN {0} USING (uuid, cloud, type) '.format(table)
        if columns:
            query += 'WHERE ' + ' AND '.join('{0} = :{0}'.format(f)
                                             for f in columns)
        return query

    @staticmethod
    def _merge_obj(columns):
        data = columns[0].data
        for col in columns[1:]:
            if col is not None:
                data.update(col.data)
        return data

    def _update_row(self, obj, table):
        pk = obj.primary_key
        uuid = pk.id
        cloud = pk.cloud
        type_name = utils.qualname(obj.get_class())
        sql_statement = \
            'INSERT OR REPLACE INTO {table} ' \
            'VALUES (:uuid, :cloud, :type_name, :data)'.format(table=table)
        self.tx.execute(sql_statement,
                        uuid=uuid, cloud=cloud, type_name=type_name,
                        data=local_db.Json(obj.dump(table)))
        obj.clear_dirty(table)
        assert not obj.is_dirty(table)

    def _store_none(self, cls, pk):
        uuid = pk.id
        cloud = pk.cloud
        type_name = utils.qualname(cls)
        self.tx.execute('INSERT OR REPLACE INTO objects '
                        'VALUES (:uuid, :cloud, :type_name, NULL)',
                        uuid=uuid, cloud=cloud, type_name=type_name)

    def _delete_rows(self, cls, cloud, object_id, table):
        predicates = []
        kwargs = {}
        if cls is not None:
            predicates.append('type=:type_name')
            kwargs['type_name'] = utils.qualname(cls)
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
        statement = 'DELETE FROM {table} WHERE '.format(table=table)
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


def _flatten_dependencies(objects, seen):
    for obj in objects:
        if obj.primary_key not in seen:
            seen.add(obj.primary_key)
            yield obj
        for dep in _flatten_dependencies(obj.dependencies(), seen):
            yield dep


def flatten_dependencies(objects):
    """
    Returns list of objects together with their dependencies.
    :param objects: Iterable of Model instances
    :return: Set of Model instances
    """
    return _flatten_dependencies(objects, set())
