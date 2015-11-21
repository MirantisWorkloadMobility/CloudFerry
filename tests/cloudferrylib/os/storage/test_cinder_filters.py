"""Tests on cinder volume filtering."""
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

import mock
from cloudferrylib.os.storage import filters

from tests import test

import datetime


DONT_CARE = mock.Mock()
TN1, TN2, TN3 = ('tn1', 'tn2', 'tn3')
VOL1, VOL2, VOL3, VOL4 = ('v1', 'v2', 'v3', 'v4')
UPD1, UPD2, UPD3, UPD4 = ('2014-11-1 00:01:41', '2014-12-31 00:00:00',
                          '2015-11-13 15:33:41', '2015-11-13 16:33:41')


def _filter_volumes(volumes, filter_yaml):
    cinder_filters = filters.CinderFilters(cinder_client=mock.MagicMock(),
                                           filter_yaml=filter_yaml)
    fs = cinder_filters.get_filters()

    for f in fs:
        volumes = [v for v in volumes if f(v)]
    return volumes


def _volume(uuid=DONT_CARE, tenant=DONT_CARE, updated_at=DONT_CARE):
    volume = {
        'id': uuid,
        'project_id': tenant,
        'updated_at': updated_at,
    }
    return volume


class CinderVolumeFilterTestCase(test.TestCase):
    def test_other_tenant_filter(self):
        volumes = (
            _volume(uuid='vol-nfs1', tenant=TN1),
        )

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = "some-other-tenant"
        filter_yaml.get_volume_ids.return_value = []
        filter_yaml.get_volume_date.return_value = None

        cinder_filters = filters.CinderFilters(cinder_client=mock.MagicMock(),
                                               filter_yaml=filter_yaml)

        fs = cinder_filters.get_filters()

        for f in fs:
            volumes = [v for v in volumes if f(v)]

        self.assertEqual(len(volumes), 0)

    def test_tenant_filter(self):
        volumes = (
            _volume(tenant=TN1),
            _volume(tenant=TN2),
            _volume(tenant=TN2),
            _volume(tenant=TN3),
        )

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = TN2
        filter_yaml.get_volume_ids.return_value = []
        filter_yaml.get_volume_date.return_value = None

        cinder_filters = filters.CinderFilters(cinder_client=mock.MagicMock(),
                                               filter_yaml=filter_yaml)

        fs = cinder_filters.get_filters()

        for f in fs:
            volumes = [v for v in volumes if f(v)]

        self.assertEqual(len(volumes),
                         len([v for v in volumes if v['project_id'] == TN2]))

    def test_volume_id_filter(self):
        volumes = (
            _volume(uuid=VOL1),
            _volume(uuid=VOL2),
            _volume(uuid=VOL3),
            _volume(uuid=VOL4),
        )

        vol_ids = [VOL1, VOL3]
        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = None
        filter_yaml.get_volume_ids.return_value = vol_ids
        filter_yaml.get_volume_date.return_value = None

        volumes = _filter_volumes(volumes, filter_yaml)

        filtered_ids = [v['id'] for v in volumes]
        self.assertIn(VOL1, filtered_ids)
        self.assertNotIn(VOL2, filtered_ids)
        self.assertIn(VOL3, filtered_ids)
        self.assertNotIn(VOL4, filtered_ids)

    def test_tenant_and_volume_id_filter(self):
        volumes = (
            _volume(uuid=VOL1, tenant=TN1),
            _volume(uuid=VOL2, tenant=TN1),
            _volume(uuid=VOL3, tenant=TN2),
            _volume(uuid=VOL4, tenant=TN1),
        )

        vol_ids = [VOL1, VOL3, VOL4]

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = TN1
        filter_yaml.get_volume_ids.return_value = vol_ids
        filter_yaml.get_volume_date.return_value = None

        volumes = _filter_volumes(volumes, filter_yaml)

        filtered_ids = [v['id'] for v in volumes]
        self.assertIn(VOL1, filtered_ids)
        self.assertNotIn(VOL2, filtered_ids)
        self.assertNotIn(VOL3, filtered_ids)
        self.assertIn(VOL4, filtered_ids)

    def test_date_and_tenant_filter(self):
        volumes = (
            _volume(uuid=VOL1, tenant=TN1, updated_at=UPD1),
            _volume(uuid=VOL2, tenant=TN1, updated_at=UPD2),
            _volume(uuid=VOL3, tenant=TN2, updated_at=UPD3),
            _volume(uuid=VOL4, tenant=TN1, updated_at=UPD4),
        )

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = TN1
        filter_yaml.get_volume_ids.return_value = []
        filter_yaml.get_volume_date.return_value = datetime.datetime.strptime(
            UPD2, filters.DATETIME_FMT)

        volumes = _filter_volumes(volumes, filter_yaml)

        filtered_ids = [v['id'] for v in volumes]

        self.assertNotIn(VOL1, filtered_ids)
        self.assertIn(VOL2, filtered_ids)
        self.assertNotIn(VOL3, filtered_ids)
        self.assertIn(VOL4, filtered_ids)

    def test_date_and_tenant_and_ids_filter(self):
        volumes = (
            _volume(uuid=VOL1, tenant=TN1, updated_at=UPD1),
            _volume(uuid=VOL2, tenant=TN1, updated_at=UPD2),
            _volume(uuid=VOL3, tenant=TN2, updated_at=UPD3),
            _volume(uuid=VOL4, tenant=TN1, updated_at=UPD4),
        )

        vol_ids = [VOL1, VOL3, VOL4]

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = TN1
        filter_yaml.get_volume_ids.return_value = vol_ids
        filter_yaml.get_volume_date.return_value = datetime.datetime.strptime(
            UPD2, filters.DATETIME_FMT)

        volumes = _filter_volumes(volumes, filter_yaml)

        filtered_ids = [v['id'] for v in volumes]
        self.assertNotIn(VOL1, filtered_ids)
        self.assertNotIn(VOL2, filtered_ids)
        self.assertNotIn(VOL3, filtered_ids)
        self.assertIn(VOL4, filtered_ids)
