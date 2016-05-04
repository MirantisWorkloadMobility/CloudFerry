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
import logging

import marshmallow
from marshmallow import fields
from oslo_utils import importutils

from cloudferry.lib.utils import bases
from cloudferry.lib.utils import query

LOG = logging.getLogger(__name__)
MODEL_LIST = [
    'cloudferry.lib.os.discovery.keystone.Tenant',
    'cloudferry.lib.os.discovery.glance.Image',
    'cloudferry.lib.os.discovery.cinder.Volume',
    'cloudferry.lib.os.discovery.nova.Server',
]
DEFAULT_MIGRATION_LIST = [
    'cloudferry.lib.os.migrate.keystone.TenantMigrationFlowFactory',
    'cloudferry.lib.os.migrate.glance.ImageMigrationFlowFactory',
    'cloudferry.lib.os.migrate.glance.ImageMemberMigrationFlowFactory',
]


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


class SshGateway(bases.Hashable, bases.Representable,
                 bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        hostname = fields.String()
        port = fields.Integer(missing=22)
        username = fields.String()
        password = fields.String(missing=None)
        private_key = fields.String(missing=None)
        gateway = fields.Nested('self', missing=None)
        connection_attempts = fields.Integer(missing=1)
        attempt_failure_sleep = fields.Float(missing=10.0)

        @marshmallow.post_load
        def to_ssh_gateway(self, data):
            return SshGateway(data)


class SshSettings(bases.Hashable, bases.Representable,
                  bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        port = fields.Integer(missing=22)
        username = fields.String(required=True)
        password = fields.String(missing=None)
        gateway = fields.Nested(SshGateway.Schema, missing=None)
        connection_attempts = fields.Integer(missing=1)
        cipher = fields.String(missing=None)
        private_key = fields.String(missing=None)
        timeout = fields.Integer(missing=600)
        attempt_failure_sleep = fields.Float(missing=10.0)

        @marshmallow.post_load
        def to_ssh_settings(self, data):
            return SshSettings(data)


class Scope(bases.Hashable, bases.Representable, bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        project_name = fields.String(missing=None)
        project_id = fields.String(missing=None)
        domain_id = fields.String(missing=None)

        @marshmallow.post_load
        def to_scope(self, data):
            return Scope(data)

        @marshmallow.validates_schema(skip_on_field_errors=True)
        def check_migration_have_correct_source_and_dict(self, data):
            if all(data[k] is None for k in self.declared_fields.keys()):
                raise marshmallow.ValidationError(
                    'At least one of {keys} shouldn\'t be None'.format(
                        keys=self.declared_fields.keys()))


class Credential(bases.Hashable, bases.Representable,
                 bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        auth_url = fields.Url()
        username = fields.String()
        password = fields.String()
        region_name = fields.String(missing=None)
        domain_id = fields.String(missing=None)
        https_insecure = fields.Boolean(missing=False)
        https_cacert = fields.String(missing=None)
        endpoint_type = fields.String(missing='admin')

        @marshmallow.post_load
        def to_credential(self, data):
            return Credential(data)


def database_settings(database_name):
    class_name = database_name.capitalize() + 'DatabaseSettings'
    global_vars = globals()
    if class_name in global_vars:
        return global_vars[class_name]

    class DatabaseSettings(bases.Hashable, bases.Representable,
                           bases.ConstructableFromDict):
        class Schema(marshmallow.Schema):
            host = fields.String(missing='localhost')
            port = fields.Integer(missing=3306)
            username = fields.String(missing=database_name)
            password = fields.String()
            database = fields.String(missing=database_name)

            @marshmallow.post_load
            def to_cloud(self, data):
                return DatabaseSettings(data)
    DatabaseSettings.__name__ = class_name
    global_vars[class_name] = DatabaseSettings
    return DatabaseSettings


class OpenstackCloud(bases.Hashable, bases.Representable,
                     bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        credential = fields.Nested(Credential.Schema)
        scope = fields.Nested(Scope.Schema)
        ssh_settings = fields.Nested(SshSettings.Schema, load_from='ssh')
        keystone_db = fields.Nested(database_settings('keystone').Schema)
        nova_db = fields.Nested(database_settings('nova').Schema,
                                required=True)
        neutron_db = fields.Nested(database_settings('neutron').Schema,
                                   required=True)
        glance_db = fields.Nested(database_settings('glance').Schema,
                                  required=True)
        cinder_db = fields.Nested(database_settings('cinder').Schema,
                                  required=True)
        discover = fields.List(fields.String(), missing=MODEL_LIST)

        @marshmallow.post_load
        def to_cloud(self, data):
            return OpenstackCloud(data)

    def __init__(self, data):
        super(OpenstackCloud, self).__init__(data)
        self.name = None


class Migration(bases.Hashable, bases.Representable):
    class Schema(marshmallow.Schema):
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
        migration_flow_factories = fields.List(fields.String(), missing=list)

        @marshmallow.post_load
        def to_migration(self, data):
            return Migration(**data)

    def __init__(self, source, destination, objects, migration_flow_factories):
        self.source = source
        self.destination = destination
        self.query = query.Query(objects)
        self.migration_flow_factories = {}

        # Migration logic can be extended through migration_flow_factories
        # migration parameter
        migration_flow_factories = \
            DEFAULT_MIGRATION_LIST + migration_flow_factories
        for factory_class_name in migration_flow_factories:
            factory_class = importutils.import_class(factory_class_name)
            migrated_class = factory_class.migrated_class
            self.migration_flow_factories[migrated_class] = factory_class


class Configuration(bases.Hashable, bases.Representable,
                    bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        clouds = DictField(
            fields.String(allow_none=False),
            fields.Nested(OpenstackCloud.Schema, default=dict))
        migrations = DictField(
            fields.String(allow_none=False),
            fields.Nested(Migration.Schema, default=dict), debug=True)

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
                        'in clouds'.format(migration_name,
                                           migration.destination))

        @marshmallow.post_load
        def to_configuration(self, data):
            for name, cloud in data['clouds'].items():
                cloud.name = name
            return Configuration(data)


def load(data):
    """
    Loads and validates configuration
    :param data: dictionary file loaded from discovery YAML
    :return: Configuration instance
    """
    schema = Configuration.Schema(strict=True)
    return schema.load(data).data
