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


from novaclient import exceptions as nova_exceptions

from cloudferrylib.base import exception as cf_exceptions
from cloudferrylib.base.action import action
from cloudferrylib.utils import log
from cloudferrylib.utils import proxy_client
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)


class CheckQuotas(action.Action):
    """Verify source and destination clouds support quotas.
    If not limited and keep usages quotas -
    do not start migration and fail with error message.
    """

    def run(self, **kwargs):
        LOG.info("Checking quotas support for SRC and DST clouds...")
        self.check_quotas(self.src_cloud)
        self.check_quotas(self.dst_cloud)
        LOG.info("SRC and DST clouds support quotas (Nova "
                 "quotas) API. Migration can proceed.")

    def check_quotas(self, cloud):
        compute_resource = cloud.resources[utils.COMPUTE_RESOURCE]
        keystone_resource = cloud.resources[utils.IDENTITY_RESOURCE]
        tenant = cloud.cloud_config['cloud']['tenant']
        ten_id = keystone_resource.get_tenant_id_by_name(tenant)
        with proxy_client.expect_exception(nova_exceptions.ClientException):
            try:
                compute_resource.nova_client.quotas.update(ten_id)
            except nova_exceptions.ClientException:
                raise cf_exceptions.AbortMigrationError(
                    "'%s' cloud does not support quotas "
                    "(Nova quotas)." % cloud.position)
