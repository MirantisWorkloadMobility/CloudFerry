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
import contextlib
import logging

import marshmallow
from marshmallow import fields

from cloudferrylib.os import clients
from cloudferrylib.utils import bases
from cloudferrylib.utils import query
from cloudferrylib.utils import remote
from cloudferrylib.utils import utils

LOG = logging.getLogger(__name__)
MODEL_LIST = [
    'cloudferrylib.os.discovery.keystone.Tenant',
    'cloudferrylib.os.discovery.glance.Image',
    'cloudferrylib.os.discovery.cinder.Volume',
    'cloudferrylib.os.discovery.nova.Server',
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


class SshSettings(bases.Hashable, bases.Representable,
                  bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        username = fields.String()
        sudo_password = fields.String(missing=None)
        gateway = fields.String(missing=None)
        connection_attempts = fields.Integer(missing=1)
        cipher = fields.String(missing=None)
        key_file = fields.String(missing=None)

        @marshmallow.post_load
        def to_scope(self, data):
            return Scope(data)


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


class OpenstackCloud(bases.Hashable, bases.Representable,
                     bases.ConstructableFromDict):
    class Schema(marshmallow.Schema):
        credential = fields.Nested(Credential.Schema)
        scope = fields.Nested(Scope.Schema)
        ssh_settings = fields.Nested(SshSettings.Schema, load_from='ssh')
        discover = OneOrMore(fields.String(), default=MODEL_LIST)

        @marshmallow.post_load
        def to_cloud(self, data):
            return OpenstackCloud(data)

    def __init__(self, data):
        super(OpenstackCloud, self).__init__(data)
        self.name = None

    def image_client(self, scope=None):
        # pylint: disable=no-member
        return clients.image_client(self.credential, scope or self.scope)

    def identity_client(self, scope=None):
        # pylint: disable=no-member
        return clients.identity_client(self.credential, scope or self.scope)

    def volume_client(self, scope=None):
        # pylint: disable=no-member
        return clients.volume_client(self.credential, scope or self.scope)

    def compute_client(self, scope=None):
        # pylint: disable=no-member
        return clients.compute_client(self.credential, scope or self.scope)

    @contextlib.contextmanager
    def remote_executor(self, hostname, key_file=None, ignore_errors=False):
        # pylint: disable=no-member
        key_files = []
        settings = self.ssh_settings
        if settings.key_file is not None:
            key_files.append(settings.key_file)
        if key_file is not None:
            key_files.append(key_file)
        if key_files:
            utils.ensure_ssh_key_added(key_files)
        try:
            yield remote.RemoteExecutor(
                hostname, settings.username,
                sudo_password=settings.sudo_password,
                gateway=settings.gateway,
                connection_attempts=settings.connection_attempts,
                cipher=settings.cipher,
                key_file=settings.key_file,
                ignore_errors=ignore_errors)
        finally:
            remote.RemoteExecutor.close_connection(hostname)


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

        @marshmallow.post_load
        def to_migration(self, data):
            return Migration(**data)

    def __init__(self, source, destination, objects):
        self.source = source
        self.destination = destination
        self.query = query.Query(objects)


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
            migrations = data['migrations']
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
