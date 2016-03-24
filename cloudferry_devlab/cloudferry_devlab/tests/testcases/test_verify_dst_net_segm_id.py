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

from cloudferry_devlab.tests import functional_test

TEST_TENANT_NAME = 'tenant4'
TEST_TENANT_NETWORKS = ['tenantnet4_segm_id_cidr1',
                        'tenantnet4_segm_id_cidr2']


class VerifyDstCloudFunctionality(functional_test.FunctionalTest):

    def setUp(self):
        super(VerifyDstCloudFunctionality, self).setUp()
        # take all segmentation ids on source and destination
        self.src_cloud.switch_user(user=self.src_cloud.username,
                                   password=self.src_cloud.password,
                                   tenant=self.src_cloud.tenant)

        self.src_all_nets_sids = []
        for net in self.src_cloud.neutronclient.list_networks()['networks']:
            if net['provider:segmentation_id']:
                self.src_all_nets_sids.append(
                    (net['name'], net['provider:segmentation_id']))

        self.dst_cloud.switch_user(user=self.dst_cloud.username,
                                   password=self.dst_cloud.password,
                                   tenant=self.dst_cloud.tenant)
        self.dst_test_tenant_id = \
            self.dst_cloud.get_tenant_id(TEST_TENANT_NAME)

        self.dst_net_sid_mapping = []
        self.dst_all_nets_sids = []
        for net in self.dst_cloud.neutronclient.list_networks()['networks']:
            if net['tenant_id'] == self.dst_test_tenant_id\
                    and net['name'] in TEST_TENANT_NETWORKS:
                self.dst_net_sid_mapping.append(
                    (net['name'], net['provider:segmentation_id']))
            elif net['provider:segmentation_id']:
                self.dst_all_nets_sids.append(
                    (net['name'], net['provider:segmentation_id']))

    def test_check_segm_id_changed_on_dst(self):
        """Validate if migrated network has unique id on both source and dst
        clouds."""
        for dst_net, dst_net_id in self.dst_net_sid_mapping:
            if dst_net_id in self.dst_all_nets_sids:
                msg = 'Network {0} migrated to destination with segmentation' \
                      'id {1} that exists on source already!'
                self.fail(msg.format(dst_net, dst_net_id))
            if dst_net_id in self.src_all_nets_sids:
                msg = 'Network {0} migrated to destination with segmentation' \
                      'id {1} that exists on destination already!'
                self.fail(msg.format(dst_net, dst_net_id))
