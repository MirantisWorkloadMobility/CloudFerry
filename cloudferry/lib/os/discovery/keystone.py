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
import json
import logging

from keystoneclient import exceptions

from cloudferry import discover
from cloudferry import model
from cloudferry.model import identity
from cloudferry.lib.os import clients
from cloudferry.lib.os import cloud_db

LOG = logging.getLogger(__name__)


class BaseKeystoneDiscoverer(discover.Discoverer):
    @property
    def _manager(self):
        raise NotImplementedError()

    def discover_all(self):
        raw_objs = self.retry(self._manager.list, returns_iterable=True)
        with model.Session() as session:
            for raw_obj in raw_objs:
                session.store(self.load_from_cloud(raw_obj))

    def discover_one(self, uuid):
        try:
            raw_obj = self.retry(self._manager.get, uuid,
                                 expected_exceptions=[exceptions.NotFound])
            with model.Session() as session:
                obj = self.load_from_cloud(raw_obj)
                session.store(obj)
                return obj
        except exceptions.NotFound:
            raise discover.NotFound()


class UserDiscoverer(BaseKeystoneDiscoverer):
    discovered_class = identity.User

    @property
    def _manager(self):
        identity_client = clients.identity_client(self.cloud)
        return identity_client.users

    def load_from_cloud(self, data):
        return identity.User.load({
            'object_id': self.make_id(data.id),
            'name': data.name,
            'enabled': data.enabled,
        })


class TenantDiscoverer(BaseKeystoneDiscoverer):
    discovered_class = identity.Tenant

    @property
    def _manager(self):
        identity_client = clients.identity_client(self.cloud)
        return identity_client.tenants

    def load_from_cloud(self, data):
        return identity.Tenant.load({
            'object_id': self.make_id(data.id),
            'name': data.name,
            'enabled': data.enabled,
            'description': data.description,
        })


class RoleDiscoverer(BaseKeystoneDiscoverer):
    discovered_class = identity.Role

    @property
    def _manager(self):
        identity_client = clients.identity_client(self.cloud)
        return identity_client.roles

    def load_from_cloud(self, data):
        return identity.Role.load({
            'object_id': self.make_id(data.id),
            'name': data.name,
        })


class UserRoleDiscoverer(discover.Discoverer):
    discovered_class = identity.UserRole

    @staticmethod
    def _is_grizzly(keystone_db):
        result = keystone_db.query('SHOW TABLES LIKE \'assignment\'')
        return len(result) == 0

    @staticmethod
    def _iterate_legacy_roles(keystone_db):
        for row in keystone_db.query(
                'SELECT `user_id`, `project_id`, `data` '
                'FROM `user_project_metadata`'):
            data = json.loads(row['data'])
            for role_id in data.get('roles', []):
                yield row['user_id'], row['project_id'], role_id

    @staticmethod
    def _iterate_modern_roles(keystone_db):
        for row in keystone_db.query(
                'SELECT `actor_id`, `target_id`, `role_id` '
                'FROM `assignment` WHERE `type`=\'UserProject\''):
            yield row['actor_id'], row['target_id'], row['role_id']

    def _iterate_roles(self, keystone_db):
        if self._is_grizzly(keystone_db):
            return self._iterate_legacy_roles(keystone_db)
        else:
            return self._iterate_modern_roles(keystone_db)

    @staticmethod
    def _make_obj(user_id, tenant_id, role_id):
        return {
            'id': ':'.join([user_id, tenant_id, role_id]),
            'tenant_id': tenant_id,
            'user_id': user_id,
            'role_id': role_id,
        }

    def discover_all(self):
        with cloud_db.connection(self.cloud.keystone_db) as ks_db:
            with model.Session() as session:
                for user_id, tenant_id, role_id in self._iterate_roles(ks_db):
                    raw_obj = self._make_obj(user_id, tenant_id, role_id)
                    session.store(self.load_from_cloud(raw_obj, no_check=True))

    def discover_one(self, uuid):
        user_id, tenant_id, role_id = uuid.split(':')
        raw_obj = self._make_obj(user_id, tenant_id, role_id)
        with model.Session() as session:
            user_role = self.load_from_cloud(raw_obj)
            session.store(user_role)
            return user_role

    def load_from_cloud(self, data, no_check=False):
        # pylint: disable=arguments-differ
        if no_check:
            make_ref = self.make_ref
        else:
            make_ref = self.find_ref

        return identity.UserRole.load({
            'object_id': self.make_id(data['id']),
            'tenant': make_ref(identity.Tenant, data['tenant_id']),
            'user': make_ref(identity.User, data['user_id']),
            'role': make_ref(identity.Role, data['role_id']),
        })
