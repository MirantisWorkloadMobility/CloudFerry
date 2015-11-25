"""Tests on cinder volume database."""
# Copyright 2014: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from cinderclient.v1 import client as cinder_client
from oslotest import mockpatch

from cloudferrylib.os.storage import cinder_database
from cloudferrylib.os.storage import filters
from cloudferrylib.utils import utils
from tests import test

TENANTS = TN1, TN2 = (
    {'id': 'tn1_id', 'name': 'tn1'},
    {'id': 'tn2_id', 'name': 'tn2'},
)


def tn_id_by_name(name):
    for tn in TENANTS:
        if tn['name'] == name:
            return tn['id']


def tn_name_by_id(uuid, _):
    for tn in TENANTS:
        if tn['id'] == uuid:
            return tn['name']

FAKE_CONFIG = utils.ext_dict(
    cloud=utils.ext_dict({'user': 'fake_user',
                          'password': 'fake_password',
                          'tenant': 'fake_tenant',
                          'host': '1.1.1.1',
                          'auth_url': 'http://1.1.1.1:35357/v2.0/',
                          'cacert': '',
                          'insecure': False}),
    migrate=utils.ext_dict({'speed_limit': '10MB',
                            'retry': '7',
                            'time_wait': 5,
                            'keep_volume_storage': False,
                            'keep_volume_snapshots': False}),
    mysql=utils.ext_dict({'db_host': '1.1.1.1'}),
    storage=utils.ext_dict({'backend': 'ceph',
                            'rbd_pool': 'volumes',
                            'volume_name_template': 'volume-',
                            'host': '1.1.1.1'}))


STATUSES = (
    AVAILABLE, IN_USE, CREATING, ERROR, DELETING, ERROR_DELETING,
    ATTACHING, DETACHING, ERROR_ATTACHING,
) = (
    'available', 'in-use', 'creating', 'error', 'deleting', 'error_deleting',
    'attaching', 'detaching', 'error_attaching',
)
DONT_CARE = mock.Mock()


def _volume(uuid=DONT_CARE, tenant=DONT_CARE, status=DONT_CARE):
    volume = {
        'id': uuid,
        'project_id': tenant,
        'status': status,
    }
    return volume


def _quota(uuid=DONT_CARE, tenant=DONT_CARE):
    quota = {
        'id': uuid,
        'project_id': tenant,
    }
    return quota


def _quota_usage(uuid=DONT_CARE, tenant=DONT_CARE):
    quota_usage = {
        'id': uuid,
        'project_id': tenant,
    }
    return quota_usage


class CinderDatabaseTestCase(test.TestCase):
    def setUp(self):
        test.TestCase.setUp(self)

        self.mock_client = mock.Mock()
        self.cs_patch = mockpatch.PatchObject(cinder_client, 'Client',
                                              new=self.mock_client)
        self.useFixture(self.cs_patch)

        self.identity_mock = mock.Mock()
        self.identity_mock.try_get_tenant_name_by_id = tn_name_by_id
        self.identity_mock.get_tenant_id_by_name = tn_id_by_name
        self.compute_mock = mock.Mock()

        self.fake_cloud = mock.Mock()
        self.fake_cloud.position = 'src'

        self.fake_cloud.resources = dict(identity=self.identity_mock,
                                         compute=self.compute_mock)
        self.cinder_client = cinder_database.CinderStorage(FAKE_CONFIG,
                                                           self.fake_cloud)
        self.mock_client().volumes.get.return_value = _volume()

    def test_volume_invalid_statuses(self):
        fake_volumes = (_volume(status=st) for st in STATUSES)
        volumes = cinder_database.skip_invalid_status_volumes(fake_volumes)
        self.assertEqual(len(volumes), len(cinder_database.VALID_STATUSES))
        for vol in volumes:
            self.assertIn(vol['status'], cinder_database.VALID_STATUSES)

    def test_get_cinder_client(self):
        # To check self.mock_client call only from this test method
        self.mock_client.reset_mock()

        client = self.cinder_client.get_client(FAKE_CONFIG)

        self.mock_client.assert_called_once_with('fake_user', 'fake_password',
                                                 'fake_tenant',
                                                 'http://1.1.1.1:35357/v2.0/',
                                                 cacert='', insecure=False)
        self.assertEqual(self.mock_client(), client)

    def test_read_db_info(self):
        fake_volumes = [
            _volume(uuid='1', tenant=TN1['id'], status='in-use'),
            _volume(uuid='2', tenant=TN2['id'], status='available'),
            _volume(uuid='3', tenant=TN2['id'], status='error'),
        ]
        fake_quotas = [
            _quota(tenant=TN1['id']),
            _quota(tenant=TN2['id']),
        ]
        fake_quota_usages = [
            _quota_usage(tenant=TN1['id']),
            _quota_usage(tenant=TN2['id']),
        ]
        fake_tables = {
            'volumes': fake_volumes,
            'quotas': fake_quotas,
            'quota_usages': fake_quota_usages,
        }
        expected_volumes = [
            _volume(uuid='1', tenant=TN1['name'], status='in-use'),
        ]
        expected_quotas = [
            _quota(tenant=TN1['name']),
        ]
        expected_quota_usages = [
            _quota_usage(tenant=TN1['name']),
        ]
        expected_tables = {
            'volumes': expected_volumes,
            'quotas': expected_quotas,
            'quota_usages': expected_quota_usages,
        }

        def get_table(table):
            return fake_tables.get(table, {})

        self.cinder_client.get_table = mock.MagicMock(side_effect=get_table)
        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = TN1['id']
        filter_yaml.get_volume_ids.return_value = []
        filter_yaml.get_volume_date.return_value = None
        self.cinder_client.volume_filter = \
            filters.CinderFilters(self.cinder_client,
                                  filter_yaml=filter_yaml)
        for table in expected_tables:
            res = self.cinder_client.list_of_dicts_for_table(table)
            self.assertEquals(res, expected_tables[table])
