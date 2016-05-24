# Copyright (c) 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

from generator import generator, generate
from nose.plugins.attrib import attr

from cloudferry_devlab.tests import functional_test


@generator
class FlavorMigrationTests(functional_test.FunctionalTest):
    """Test Case class which includes flavor's migration cases."""

    def setUp(self):
        super(FlavorMigrationTests, self).setUp()

        self.src_public_flavors = self.filter_flavors()
        self.dst_public_flavors = self.dst_cloud.novaclient.flavors.list()

        self.src_private_flavors = self.filter_flavors(
            filter_only_private=True)
        self.dst_private_flavors = self.dst_cloud.novaclient.flavors.list(
            is_public=False)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    @generate('name', 'ram', 'vcpus', 'disk', 'id', 'rxtx_factor', 'swap',
              'OS-FLV-EXT-DATA:ephemeral', 'OS-FLV-DISABLED:disabled')
    def test_migrate_public_flavors(self, param):
        """Validate public flavors with parameters were migrated correct.

        :param name: flavor name
        :param ram: RAM amount set for flavor
        :param vcpus: Virtual CPU's amount
        :param disk: disk size
        :param id: flavor's id
        :param rxtx_factor: rxtx factor
        :param swap: swap size
        :param ephemeral: ephemeral size
        :param disabled: disabled flavor"""
        self.validate_resource_parameter_in_dst(self.src_public_flavors,
                                                self.dst_public_flavors,
                                                'flavor', param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    @generate('name', 'ram', 'vcpus', 'disk', 'id', 'rxtx_factor', 'swap',
              'OS-FLV-EXT-DATA:ephemeral', 'OS-FLV-DISABLED:disabled')
    def test_migrate_private_flavors(self, param):
        """Validate private flavors with parameters were migrated correct.

        List of parameters is the same as for public flavors.
        """
        self.validate_resource_parameter_in_dst(self.src_private_flavors,
                                                self.dst_private_flavors,
                                                'flavor', param)
