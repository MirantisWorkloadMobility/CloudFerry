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


class CheckAffinity(action.Action):
    """Verify whether source and destination clouds support affinity and
    anti-affinity API (Nova server groups). If affinity/anti-affinity API are
    not supported - do not start migration and fail with error message.
    """

    def run(self, **kwargs):
        LOG.info("Checking affinity/anti-affinity (Nova server groups) API "
                 "support for SRC and DST clouds...")

        if not self.cfg.migrate.keep_affinity_settings:
            LOG.info("Affinity settings will not be migrated due to the config"
                     " (keep_affinity_settings = False). Skipping this check.")
            return

        check_affinity_api(self.src_cloud)
        check_affinity_api(self.dst_cloud)

        LOG.info("SRC and DST clouds support affinity/anti-affinity (Nova "
                 "server groups) API. Migration can proceed.")


def check_affinity_api(cloud):
    compute_resource = cloud.resources[utils.COMPUTE_RESOURCE]
    with proxy_client.expect_exception(nova_exceptions.NotFound):
        try:
            compute_resource.nova_client.server_groups.list()
        except nova_exceptions.NotFound:
            raise cf_exceptions.AbortMigrationError(
                "'%s' cloud does not support affinity/anti-affinity "
                "(Nova server groups) API." % cloud.position)
