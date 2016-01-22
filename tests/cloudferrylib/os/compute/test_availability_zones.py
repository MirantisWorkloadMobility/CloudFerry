# Copyright 2016 Mirantis Inc.
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

import StringIO

from mock import mock
from novaclient import exceptions

from cloudferrylib.os.compute import availability_zones

from tests import test


class AvailabilityZoneMapperTestCase(test.TestCase):
    def test_returns_zone_if_present(self):
        mapping = """
        src_az1: dst_z2
        src_az2: dst_z3
        src_az3: dst_z4
        $$default: nova
        """

        zone = 'expected zone'
        expected_zone = zone
        az_map = StringIO.StringIO(mapping)
        nc = mock.Mock()
        nc.availability_zone.find.return_value = expected_zone

        azm = availability_zones.AvailabilityZoneMapper(nc, az_map)

        actual_az = azm.get_availability_zone(zone)

        self.assertEqual(actual_az, expected_zone)

    def test_returns_mapped_zone_if_zone_not_present_in_destination(self):
        expected_zone = 'expected zone'
        not_in_dst = 'zone_not_present_in_dest'

        mapping = """
        src_az1: dst_z2
        src_az2: dst_z3
        src_az3: dst_z4
        {not_present}: {expected}
        $$default: nova
        """.format(not_present=not_in_dst,
                   expected=expected_zone)

        az_map = StringIO.StringIO(mapping)
        nc = mock.Mock()
        nc.availability_zones.find.side_effect = exceptions.NotFound("")

        azm = availability_zones.AvailabilityZoneMapper(nc, az_map)

        actual_az = azm.get_availability_zone(not_in_dst)

        self.assertEqual(actual_az, expected_zone)

    def test_returns_default_if_map_doesnt_have_explicit_mapping(self):
        expected_zone = 'default zone'
        not_in_dst = 'zone_not_present_in_dest'

        mapping = """
        src_az1: dst_z2
        src_az2: dst_z3
        src_az3: dst_z4
        $$default: {default}
        """.format(default=expected_zone)

        az_map = StringIO.StringIO(mapping)
        nc = mock.Mock()
        nc.availability_zones.find.side_effect = exceptions.NotFound("")

        azm = availability_zones.AvailabilityZoneMapper(nc, az_map)

        actual_az = azm.get_availability_zone(not_in_dst)

        self.assertEqual(actual_az, expected_zone)

    def test_returns_none_for_none_argument(self):
        mapping = """
        src_az1: dst_z2
        src_az2: dst_z3
        src_az3: dst_z4
        $$default: anything
        """

        az_map = StringIO.StringIO(mapping)
        nc = mock.Mock()

        azm = availability_zones.AvailabilityZoneMapper(nc, az_map)

        self.assertIsNone(azm.get_availability_zone(None))
