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

from cloudferry.lib.os.network import neutron
from cloudferry.lib.utils import utils

from tests import test


class FakeSGRule(dict):
    def __init__(self, ip_prefix, **kwargs):
        super(FakeSGRule, self).__init__(**kwargs)
        self['remote_ip_prefix'] = ip_prefix
        self['ethertype'] = 'IPv4' if ip_prefix.count('.') == 3 else 'IPv6'

    def __getitem__(self, item):
        if item not in self:
            return "don't care"
        return super(FakeSGRule, self).__getitem__(item)


class RemoteIPPrefixConvertSecurityGroupRulesTestCase(test.TestCase):
    def _ip_prefixes_assertion(self, remote_ip1, remote_ip2, valid, equal):
        rule1 = FakeSGRule(remote_ip1)
        rule2 = FakeSGRule(remote_ip2)

        nn = mock.MagicMock()
        nm = mock.Mock()
        nm.get_resource_hash = neutron.NeutronNetwork.get_resource_hash
        nn.resources = {utils.NETWORK_RESOURCE: nm}

        r1 = neutron.NeutronNetwork.convert_rules(rule1, nn)
        r2 = neutron.NeutronNetwork.convert_rules(rule2, nn)

        is_equal = self.assertEqual if equal else self.assertNotEqual
        is_none = self.assertIsNotNone if valid else self.assertIsNone

        is_equal(r1, r2)
        is_equal(r1['rule_hash'], r2['rule_hash'])
        is_none(r1['remote_ip_prefix'])
        is_none(r2['remote_ip_prefix'])

    def _remote_ip_prefixes_are_equal(self, getitem1, getitem2, valid=True):
        self._ip_prefixes_assertion(getitem1, getitem2, valid, equal=True)

    def _remote_ip_prefixes_differ(self, getitem1, getitem2, valid=True):
        self._ip_prefixes_assertion(getitem1, getitem2, valid, equal=False)

    def test_remote_ipv6_address_are_different(self):
        ipv6_1 = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        ipv6_2 = '2222:0db8:85a3:0000:0000:8a2e:0370:7334'
        self._remote_ip_prefixes_differ(ipv6_1, ipv6_2)

    def test_remote_ipv6_address_equal(self):
        ipv6_1 = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        ipv6_2 = '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
        self._remote_ip_prefixes_are_equal(ipv6_1, ipv6_2)

    def test_remote_ipv4_addresses_differ(self):
        ip1 = '1.2.3.4'
        ip2 = '4.5.5.6/32'
        self._remote_ip_prefixes_differ(ip1, ip2)

    def test_remote_ip_with_invalid_bitmasks_are_equal(self):
        invalid = '1.2.3.4/999'
        self._remote_ip_prefixes_are_equal(invalid, invalid, valid=False)

    def test_remote_ip_with_no_bitmasks_are_equal(self):
        no_bitmask = '1.2.3.4'
        self._remote_ip_prefixes_are_equal(no_bitmask, no_bitmask)

    def test_remote_ip_with_bitmasks_are_equal(self):
        bitmask = '1.2.3.4/24'
        self._remote_ip_prefixes_are_equal(bitmask, bitmask)

    def test_remote_ip_with_bitmask_equals_no_bitmask(self):
        bitmask = '1.2.3.4/32'
        no_bitmask = '1.2.3.4'
        self._remote_ip_prefixes_are_equal(bitmask, no_bitmask)
