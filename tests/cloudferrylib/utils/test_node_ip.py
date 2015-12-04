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

from mock import patch

from cloudferrylib.utils import node_ip

from tests import test


class NodeIPTestCase(test.TestCase):
    @patch("cloudferrylib.utils.node_ip.socket")
    @patch.object(node_ip, "get_ips")
    def test_falls_back_to_node_ip(self, get_ips_mock, socket_mock):
        ext_cidr = ["10.0.0.0/24"]
        init_host = "controller"
        compute_host = "compute"
        user = "user"
        expected = "192.168.1.3"

        get_ips_mock.return_value = []
        socket_mock.gethostbyname.return_value = expected

        ip = node_ip.get_ext_ip(ext_cidr, init_host, compute_host, user)

        self.assertEqual(expected, ip)

    @patch.object(node_ip, "get_ips")
    def test_returns_correct_ip_if_available(self, get_ips_mock):
        ext_cidr = ["10.0.0.0/24"]
        init_host = "controller"
        compute_host = "compute"
        user = "user"
        expected = "10.0.0.100"

        get_ips_mock.return_value = [expected, "1.2.3.4", "5.6.7.8"]

        ip = node_ip.get_ext_ip(ext_cidr, init_host, compute_host, user)

        self.assertEqual(expected, ip)
