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
import collections
import itertools
import logging

import marshmallow
from marshmallow import fields
from oslo_utils import importutils

from cloudferry.lib.utils import bases
from cloudferry.lib.utils import query

LOG = logging.getLogger(__name__)
DEFAULT_MIGRATION_LIST = [
    'cloudferry.lib.os.migrate.keystone.TenantMigrationFlowFactory',
    'cloudferry.lib.os.migrate.glance.ImageMigrationFlowFactory',
    'cloudferry.lib.os.migrate.glance.ImageMemberMigrationFlowFactory',
]
DEFAULT_DISCOVERER_LIST = [
    'cloudferry.lib.os.discovery.keystone.TenantDiscoverer',
    'cloudferry.lib.os.discovery.glance.ImageDiscoverer',
    'cloudferry.lib.os.discovery.glance.ImageMemberDiscoverer',
    'cloudferry.lib.os.discovery.cinder.VolumeDiscoverer',
    'cloudferry.lib.os.discovery.cinder.AttachmentDiscoverer',
    'cloudferry.lib.os.discovery.nova.FlavorDiscoverer',
    'cloudferry.lib.os.discovery.nova.ServerDiscoverer',
]


class ValidationError(bases.ExceptionWithFormatting):
    pass


class ConfigSchema(marshmallow.Schema):
    config_section_class = None

    @marshmallow.validates_schema(pass_original=True)
    def check_unknown_fields(self, _, original_data):
        possible_fields = set()
        for field_name, field in self.fields.items():
            possible_fields.add(field.load_from or field_name)
        for key in original_data:
            if key not in possible_fields:
                raise ValidationError(
                    'Unknown field provided for %s: %s' % (
                        self.config_section_class.__name__, key))

    @marshmallow.post_load
    def to_config_section(self, data):
        # pylint: disable=not-callable
        assert self.config_section_class is not None
        return self.config_section_class(**data)

    def handle_error(self, error, data):
        # super(ConfigSchema, self).handle_error(error, data)
        result = []
        self._format_messages(result, [], error.message)
        raise ValidationError(*result)

    @classmethod
    def _format_messages(cls, result, keys, messages):
        # According to marshmallow docs, error.message can be an error message,
        # list of error messages, or dict of error messages.
        if isinstance(messages, dict):
            cls._format_error_dict(result, keys, messages)
        elif isinstance(messages, list):
            cls._format_error_list(result, keys, messages)
        elif isinstance(messages, basestring):
            cls._format_error_str(result, keys, messages)

    @classmethod
    def _format_error_dict(cls, result, keys, messages):
        assert isinstance(messages, dict)
        for field, message in messages.items():
            cls._format_messages(result, keys + [field], message)

    @classmethod
    def _format_error_list(cls, result, keys, messages):
        assert isinstance(messages, list)
        for message in messages:
            cls._format_messages(result, keys, message)

    @classmethod
    def _format_error_str(cls, result, keys, message):
        assert isinstance(message, basestring)
        if keys:
            result.append(
                'Error in {classname}:{keys}: {message}'.format(
                    classname=cls.config_section_class.__name__,
                    keys='->'.join(keys), message=message))
        else:
            result.append(message)


class ConfigSectionMetaclass(type):
    def __new__(mcs, name, parents, dct):
        schema_class = None
        if parents == (ConfigSchema,):
            # Trick to make pylint think that ConfigSection subclasses have all
            # the methods of Schema so that it can check various methods that
            # will go to schema (like marshmallow.validates_*).
            parents = (bases.Hashable, bases.Representable)
        else:
            schema_fields = {}
            for key in dct:
                value = dct[key]
                if isinstance(value, fields.FieldABC) or \
                        hasattr(value, '__marshmallow_tags__'):
                    schema_fields[key] = value
            for key in schema_fields:
                del dct[key]

            schema_class = type(name + 'Schema', (ConfigSchema,),
                                schema_fields)
            dct['schema_class'] = schema_class
        config_section_class = super(ConfigSectionMetaclass, mcs).__new__(
            mcs, name, parents, dct)
        if schema_class is not None:
            schema_class.config_section_class = config_section_class
        return config_section_class


class ConfigSection(ConfigSchema):
    __metaclass__ = ConfigSectionMetaclass
    schema_class = None

    def __init__(self, **kwargs):
        super(ConfigSection, self).__init__()
        # pylint: disable=not-callable
        if self.schema_class is None:
            return
        for field_name in self.schema_class().fields:  # pyling
            if not hasattr(self, field_name):
                setattr(self, field_name, kwargs.pop(field_name))
        assert not kwargs, 'kwargs should only contain field values'


class ClassList(fields.Field):
    default_error_messages = {
        'import': 'failed to import {classname}'
    }

    def __init__(self, initial_list):
        super(ClassList, self).__init__(missing=list)
        self.initial_list = initial_list

    def _deserialize(self, value, attr, data):
        if not isinstance(value, list):
            self.fail('type')

        result = []
        for class_qualname in itertools.chain(self.initial_list, value):
            try:
                result.append(importutils.import_class(class_qualname))
            except ImportError:
                self.fail('import', classname=class_qualname)
        return result


class DictField(fields.Field):
    def __init__(self, key_field, nested_field, **kwargs):
        super(DictField, self).__init__(**kwargs)
        self.key_field = key_field
        self.nested_field = nested_field

    def _deserialize(self, value, attr, data):
        if not isinstance(value, dict):
            self.fail('type')

        ret = {}
        for key, val in value.items():
            k = self.key_field.deserialize(key)
            v = self.nested_field.deserialize(val)
            ret[k] = v
        return ret


class FirstFit(fields.Field):
    def __init__(self, *args, **kwargs):
        many = kwargs.pop('many', False)
        super(FirstFit, self).__init__(**kwargs)
        self.many = many
        self.variants = args

    def _deserialize(self, value, attr, data):
        if self.many:
            return [self._do_deserialize(v) for v in value]
        else:
            return self._do_deserialize(value)

    def _do_deserialize(self, value):
        errors = []
        for field in self.variants:
            try:
                return field.deserialize(value)
            except marshmallow.ValidationError as ex:
                errors.append(ex)
        raise marshmallow.ValidationError([e.messages for e in errors])


class OneOrMore(fields.Field):
    def __init__(self, base_type, **kwargs):
        super(OneOrMore, self).__init__(**kwargs)
        self.base_type = base_type

    def _deserialize(self, value, attr, data):
        # pylint: disable=protected-access
        if isinstance(value, collections.Sequence) and \
                not isinstance(value, basestring):
            return [self.base_type._deserialize(v, attr, data)
                    for v in value]
        else:
            return [self.base_type._deserialize(value, attr, data)]


class SshGateway(ConfigSection):
    hostname = fields.String()
    port = fields.Integer(missing=22)
    username = fields.String()
    password = fields.String(missing=None)
    private_key = fields.String(missing=None)
    gateway = fields.Nested('self', missing=None)


class SshSettings(ConfigSection):
    port = fields.Integer(missing=22)
    username = fields.String(required=True)
    password = fields.String(missing=None)
    gateway = fields.Nested(SshGateway.schema_class, missing=None)
    connection_attempts = fields.Integer(missing=1)
    cipher = fields.String(missing=None)
    private_key = fields.String(missing=None)
    timeout = fields.Integer(missing=600)
    attempt_failure_sleep = fields.Float(missing=10.0)


class Scope(ConfigSection):
    project_name = fields.String(missing=None)
    project_id = fields.String(missing=None)
    domain_id = fields.String(missing=None)

    @marshmallow.validates_schema(skip_on_field_errors=True)
    def check_migration_have_correct_source_and_dict(self, data):
        if all(data[k] is None for k in self.fields.keys()):
            raise ValidationError('At least one of %s shouldn\'t be None',
                                  self.fields.keys())


class Credential(ConfigSection):
    auth_url = fields.Url()
    username = fields.String()
    password = fields.String()
    region_name = fields.String(missing=None)
    domain_id = fields.String(missing=None)
    https_insecure = fields.Boolean(missing=False)
    https_cacert = fields.String(missing=None)
    endpoint_type = fields.String(missing='admin')


def database_settings(database_name):
    class_name = database_name.capitalize() + 'DatabaseSettings'
    global_vars = globals()
    if class_name in global_vars:
        return global_vars[class_name]

    class DatabaseSettings(ConfigSection):
        host = fields.String(missing='localhost')
        port = fields.Integer(missing=3306)
        username = fields.String(missing=database_name)
        password = fields.String()
        database = fields.String(missing=database_name)

    DatabaseSettings.__name__ = class_name
    global_vars[class_name] = DatabaseSettings
    return DatabaseSettings


class OpenstackCloud(ConfigSection):
    name = fields.String()
    request_attempts = fields.Integer(missing=3)
    request_failure_sleep = fields.Float(missing=5)
    credential = fields.Nested(Credential.schema_class)
    scope = fields.Nested(Scope.schema_class)
    ssh_settings = fields.Nested(SshSettings.schema_class, load_from='ssh')
    discoverers = ClassList(DEFAULT_DISCOVERER_LIST)

    keystone_db = fields.Nested(database_settings('keystone').schema_class,
                                required=True)
    nova_db = fields.Nested(database_settings('nova').schema_class,
                            required=True)
    neutron_db = fields.Nested(database_settings('neutron').schema_class,
                               required=True)
    glance_db = fields.Nested(database_settings('glance').schema_class,
                              required=True)
    cinder_db = fields.Nested(database_settings('cinder').schema_class,
                              required=True)

    def __init__(self, **kwargs):
        self.discoverers = collections.OrderedDict()
        for discoverer_cls in kwargs.pop('discoverers'):
            self.discoverers[discoverer_cls.discovered_class] = discoverer_cls
        super(OpenstackCloud, self).__init__(**kwargs)


class Migration(ConfigSection):
    source = fields.String(required=True)
    destination = fields.String(required=True)
    objects = DictField(
        fields.String(),
        FirstFit(
            fields.String(),
            DictField(
                fields.String(),
                OneOrMore(fields.Raw())),
            many=True),
        required=True)
    migration_flow_factories = ClassList(DEFAULT_MIGRATION_LIST)

    def __init__(self, source, destination, objects, migration_flow_factories,
                 **kwargs):
        self.source = source
        self.destination = destination
        self.query = query.Query(objects)
        self.migration_flow_factories = {}

        # Migration logic can be extended through migration_flow_factories
        # migration parameter
        for factory_class in migration_flow_factories:
            migrated_class = factory_class.migrated_class
            self.migration_flow_factories[migrated_class] = factory_class
        super(Migration, self).__init__(objects=objects, **kwargs)


class Configuration(ConfigSection):
    clouds = DictField(
        fields.String(allow_none=False),
        fields.Nested(OpenstackCloud.schema_class, default=dict))
    migrations = DictField(
        fields.String(allow_none=False),
        fields.Nested(Migration.schema_class, default=dict), debug=True)

    @marshmallow.validates_schema(skip_on_field_errors=True)
    def check_migration_have_correct_source_and_dict(self, data):
        clouds = data['clouds']
        migrations = data.get('migrations', {})
        for migration_name, migration in migrations.items():
            if migration.source not in clouds:
                raise marshmallow.ValidationError(
                    'Migration "{0}" source "{1}" should be defined '
                    'in clouds'.format(migration_name, migration.source))
            if migration.destination not in clouds:
                raise marshmallow.ValidationError(
                    'Migration "{0}" destination "{1}" should be defined '
                    'in clouds'.format(migration_name, migration.destination))

    @marshmallow.pre_load
    def populate_cloud_names(self, data):
        clouds = data['clouds']
        for name, cloud in list(clouds.items()):
            cloud = dict(cloud)
            clouds[name] = cloud
            cloud['name'] = name


def load(data):
    """
    Loads and validates configuration
    :param data: dictionary file loaded from discovery YAML
    :return: Configuration instance
    """
    # pylint: disable=not-callable
    schema = Configuration.schema_class(strict=True)
    return schema.load(data).data
