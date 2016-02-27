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

import mock

from cloudferrylib.os.storage.plugins.iscsi import iscsi

from tests import test


class VolumeParamsTestCase(test.TestCase):
    def test_volume_params_built_from_iscsiadm_output(self):
        expected_portal = "172.29.65.23:3260"
        expected_lun = 1
        expected_iqn = "iqn.1992-04.com.emc:5000097300273190"
        out = '{portal},{lun} {iqn}'.format(portal=expected_portal,
                                            lun=expected_lun,
                                            iqn=expected_iqn)

        vp = iscsi.VolumeParams.from_iscsiadm_string(out)

        self.assertIsInstance(vp, iscsi.VolumeParams)

        self.assertEqual(expected_iqn, vp.target_iqn)
        self.assertEqual(expected_lun, vp.target_lun)
        self.assertEqual(expected_portal, vp.target_portal)

    def test_works_with_session_output(self):
        expected_portal = "172.29.65.22:3260"
        expected_lun = 1
        expected_iqn = "172.29.65.22:3260"
        out = "tcp: [1] {portal},{lun} {iqn}".format(
            portal=expected_portal, lun=expected_lun, iqn=expected_iqn)
        vp = iscsi.VolumeParams.from_iscsiadm_string(out)

        self.assertIsInstance(vp, iscsi.VolumeParams)

        self.assertEqual(expected_iqn, vp.target_iqn)
        self.assertEqual(expected_lun, vp.target_lun)
        self.assertEqual(expected_portal, vp.target_portal)


class ISCSIConnectorTestCase(test.TestCase):
    @mock.patch("cloudferrylib.os.storage.plugins.iscsi.iscsi.local."
                "sudo_ignoring_errors")
    def test_sessions_returns_correct_list_of_volume_params(self, sudo_mock):
        out = """
        tcp: [1] 172.29.65.22:3260,1 iqn.1992-04.com.emc:500009730027c990
        tcp: [2] 172.29.65.36:3260,1 iqn.1992-04.com.emc:500009730027c994
        tcp: [3] 172.29.65.35:3260,1 iqn.1992-04.com.emc:500009730027c954
        tcp: [4] 172.29.65.38:3260,1 iqn.1992-04.com.emc:500009730027c91c
        tcp: [5] 172.29.65.39:3260,1 iqn.1992-04.com.emc:500009730027c95c
        tcp: [6] 172.29.65.26:3260,1 iqn.1992-04.com.emc:500009730027c998
        tcp: [7] 172.29.65.34:3260,1 iqn.1992-04.com.emc:500009730027c914
        """

        sudo_mock.return_value = 0, out

        connector = iscsi.ISCSIConnector(storage_backend_timeout=0)
        sessions = connector.get_sessions()

        self.assertIsInstance(sessions, list)
        self.assertEqual(7, len(sessions))
        self.assertTrue(all([isinstance(s, iscsi.VolumeParams)
                             for s in sessions]))
