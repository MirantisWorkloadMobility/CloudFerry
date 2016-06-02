# Copyright 2015 Mirantis Inc.
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
from cloudferry import config
from cloudferry import discover
from tests import test

REGULAR_MIGRATION = {
    'source': 'foo',
    'destination': 'bar',
    'objects': {'vms': [{'tenant.name': 'foo'}]}
}
REGULAR_CREDENTIAL = {
    'auth_url': 'https://keystone.example.com',
    'username': 'admin',
    'password': 'secret',
    'region_name': 'region1',
    'domain_id': 'dom',
    'https_insecure': True,
    'https_cacert': 'wtf',
}
REGULAR_SSH_GATEWAY = {
    'hostname': 'gw.example.com',
    'port': 123,
    'username': 'admin',
    'password': 'secret',
}
REGULAR_SSH_SETTINGS = {
    'port': 222,
    'username': 'admin',
    'password': 'secret',
    'gateway': REGULAR_SSH_GATEWAY,
    'connection_attempts': 4,
    'attempt_failure_sleep': 60.0,
    'cipher': 'rc4',
    'timeout': 123,
}
REGULAR_DB_SETTINGS = {
    'host': 'mysql.example.com',
    'username': 'root',
    'password': 'secret',
}


class ConfigTestCase(test.TestCase):
    @staticmethod
    def _load(section_cls, data):
        schema = section_cls.schema_class(strict=True)
        return schema.load(data).data


class SshGatewayTestCase(ConfigTestCase):
    def test_regular(self):
        ssh_gw = self._load(config.SshGateway, REGULAR_SSH_GATEWAY)
        self.assertIsInstance(ssh_gw, config.SshGateway)
        self.assertAttrs(ssh_gw,
                         hostname='gw.example.com',
                         port=123,
                         username='admin',
                         password='secret',
                         private_key=None,
                         gateway=None)

    def test_nested(self):
        ssh_gw = self._load(config.SshGateway, {
            'hostname': 'gw2.example.com',
            'username': 'admin2',
            'password': 'secret2',
            'gateway': REGULAR_SSH_GATEWAY
        })
        self.assertIsInstance(ssh_gw, config.SshGateway)
        self.assertIsNotNone(ssh_gw)
        self.assertIsInstance(ssh_gw.gateway, config.SshGateway)
        self.assertAttrs(ssh_gw,
                         hostname='gw2.example.com',
                         port=22,
                         username='admin2',
                         password='secret2',
                         private_key=None)
        self.assertAttrs(ssh_gw.gateway,
                         hostname='gw.example.com',
                         port=123,
                         username='admin',
                         password='secret',
                         private_key=None,
                         gateway=None)


class SshSettingsTestCase(ConfigTestCase):
    def test_regular(self):
        ssh_settings = self._load(config.SshSettings, REGULAR_SSH_SETTINGS)
        self.assertIsInstance(ssh_settings, config.SshSettings)
        self.assertAttrs(ssh_settings,
                         port=222,
                         username='admin',
                         password='secret',
                         connection_attempts=4,
                         attempt_failure_sleep=60.0,
                         cipher='rc4',
                         timeout=123)
        self.assertAttrs(ssh_settings.gateway,
                         hostname='gw.example.com',
                         port=123,
                         username='admin',
                         password='secret',
                         private_key=None,
                         gateway=None)


class ScopeTestCase(ConfigTestCase):
    def test_regular(self):
        scope = self._load(config.Scope, {
            'project_name': 'foo'
        })
        self.assertIsInstance(scope, config.Scope)
        self.assertAttrs(scope,
                         project_name='foo',
                         project_id=None,
                         domain_id=None)

    def test_regular2(self):
        scope = self._load(config.Scope, {
            'project_id': 'foo'
        })
        self.assertIsInstance(scope, config.Scope)
        self.assertAttrs(scope,
                         project_name=None,
                         project_id='foo',
                         domain_id=None)

    def test_regular3(self):
        scope = self._load(config.Scope, {
            'domain_id': 'foo'
        })
        self.assertIsInstance(scope, config.Scope)
        self.assertAttrs(scope,
                         project_name=None,
                         project_id=None,
                         domain_id='foo')

    def test_something_should_be_specified(self):
        self.assertRaises(config.ValidationError, self._load, config.Scope, {})


class CredentialTestCase(ConfigTestCase):
    def test_regular(self):
        cred = self._load(config.Credential, REGULAR_CREDENTIAL)
        self.assertIsInstance(cred, config.Credential)
        self.assertAttrs(cred,
                         auth_url='https://keystone.example.com',
                         username='admin',
                         password='secret',
                         region_name='region1',
                         domain_id='dom',
                         https_insecure=True,
                         https_cacert='wtf',
                         endpoint_type='admin')


class OpenstackCloudTestCase(ConfigTestCase):
    def test_regular(self):
        cloud = self._load(config.OpenstackCloud, {
            'name': 'foo',
            'credential': REGULAR_CREDENTIAL,
            'scope': {'project_name': 'foo'},
            'ssh': REGULAR_SSH_SETTINGS,
            'keystone_db': REGULAR_DB_SETTINGS,
            'nova_db': REGULAR_DB_SETTINGS,
            'neutron_db': REGULAR_DB_SETTINGS,
            'glance_db': REGULAR_DB_SETTINGS,
            'cinder_db': REGULAR_DB_SETTINGS,
        })
        self.assertIsInstance(cloud, config.OpenstackCloud)
        self.assertAttrs(cloud, name='foo')
        for key in ('keystone_db', 'nova_db', 'neutron_db', 'glance_db',
                    'cinder_db'):
            self.assertAttrs(getattr(cloud, key),
                             host='mysql.example.com',
                             port=3306,
                             username='root',
                             password='secret',
                             database=key[:-3])
        for model_class, discoverer in cloud.discoverers.items():
            self.assertIs(model_class, discoverer.discovered_class)
            self.assertTrue(issubclass(discoverer, discover.Discoverer))


class MigrationTestCase(ConfigTestCase):
    def test_regular(self):
        migration = self._load(config.Migration, REGULAR_MIGRATION)
        self.assertIsInstance(migration, config.Migration)
        self.assertAttrs(migration, source='foo', destination='bar')


class ConfigurationTestCase(ConfigTestCase):
    VALID_CLOUD = {
        'credential': REGULAR_CREDENTIAL,
        'scope': {'project_name': 'foo'},
        'ssh': REGULAR_SSH_SETTINGS,
        'keystone_db': REGULAR_DB_SETTINGS,
        'nova_db': REGULAR_DB_SETTINGS,
        'neutron_db': REGULAR_DB_SETTINGS,
        'glance_db': REGULAR_DB_SETTINGS,
        'cinder_db': REGULAR_DB_SETTINGS,
    }

    def test_regular(self):
        conf = self._load(config.Configuration, {
            'migrations': {'foo_bar': REGULAR_MIGRATION},
            'clouds': {
                'foo': self.VALID_CLOUD,
                'bar': self.VALID_CLOUD,
            },

        })
        self.assertIsInstance(conf, config.Configuration)
        self.assertEqual('foo', conf.clouds['foo'].name)
        self.assertEqual('bar', conf.clouds['bar'].name)

    def test_missing_source_migration(self):
        self.assertRaises(config.ValidationError, config.load, {
            'migrations': {'foo_bar': REGULAR_MIGRATION},
            'clouds': {
                'bar': self.VALID_CLOUD,
            },
        })

    def test_missing_destination_migration(self):
        self.assertRaises(config.ValidationError, config.load, {
            'migrations': {'foo_bar': REGULAR_MIGRATION},
            'clouds': {
                'foo': self.VALID_CLOUD,
            },
        })

    def test_unexpected_field(self):
        self.assertRaises(config.ValidationError, config.load, {
            'foo': 'bar',
            'migrations': {'foo_bar': REGULAR_MIGRATION},
            'clouds': {
                'foo': self.VALID_CLOUD,
                'bar': self.VALID_CLOUD,
            },
        })
