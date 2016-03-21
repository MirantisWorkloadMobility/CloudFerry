# Copyright (c) 2015 Mirantis Inc.
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


from cloudferrylib.base.action import action
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)


class CheckConfigQuotaNeutron(action.Action):
    """
    Checking config quotas between src and dst clouds.

    If all tenants have customs quotas then different configurations does not
    matter.
    """

    def run(self, info=None, **kwargs):
        src_cloud = self.src_cloud
        dst_cloud = self.dst_cloud
        network_src = src_cloud.resources[utl.NETWORK_RESOURCE]
        identity_dst = dst_cloud.resources[utl.IDENTITY_RESOURCE]
        network_dst = dst_cloud.resources[utl.NETWORK_RESOURCE]

        search_opts_tenant = kwargs.get('search_opts_tenant', {})
        tenants_src = self.get_src_tenants(search_opts_tenant)

        list_quotas = network_src.list_quotas()
        tenants_without_quotas = self.get_tenants_without_quotas(tenants_src,
                                                                 list_quotas)
        if not tenants_without_quotas:
            LOG.info("On SRC cloud all tenants "
                     "have custom quotas for network")
            LOG.info("Difference between clouds configs "
                     "default quotas will not calculated")
            LOG.info("Migration can proceed")
            return
        LOG.info("Checking default quota "
                 "configuration on source and destination cloud")
        quot = network_src.show_quota(tenants_without_quotas[0])
        dst_temp_tenant = identity_dst.create_tenant("Test Tenant For Quotas")
        quot_default_dst = network_dst.show_quota(dst_temp_tenant.id)
        is_configs_different = False
        identity_dst.delete_tenant(dst_temp_tenant)
        for item_quot, val_quot in quot.iteritems():
            if val_quot != quot_default_dst[item_quot]:
                is_configs_different = True
                LOG.info("Item %s in quotas is different "
                         "(SRC CLOUD: %s, DST CLOUD: %s)" %
                         (item_quot,
                          val_quot,
                          quot_default_dst[item_quot]))
        if not is_configs_different:
            LOG.info("Configs on clouds is equals")

    @staticmethod
    def get_tenants_without_quotas(tenants_src, list_quotas):
        tenants_ids = tenants_src.keys()
        quotas_ids_tenants = [quota["tenant_id"] for quota in list_quotas]
        return list(set(tenants_ids) - set(quotas_ids_tenants))

    def get_src_tenants(self, search_opts):
        identity_src = self.src_cloud.resources[utl.IDENTITY_RESOURCE]

        if search_opts.get('tenant_id'):
            filter_tenants_ids_list = search_opts['tenant_id']
            tenants = [identity_src.keystone_client.tenants.find(id=tnt_id) for
                       tnt_id in filter_tenants_ids_list]
        else:
            tenants = identity_src.get_tenants_list()

        tenants_dict = {tenant.id: tenant.name for tenant in tenants}

        return tenants_dict
