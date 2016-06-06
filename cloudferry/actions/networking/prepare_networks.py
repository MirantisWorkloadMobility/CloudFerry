# Copyright (c) 2014 Mirantis Inc.
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


from cloudferry.lib.base.action import action
from cloudferry.lib.os.network import network_utils
from cloudferry.lib.utils import log
from cloudferry.lib.utils import utils

LOG = log.getLogger(__name__)


class PrepareNetworks(action.Action):
    """Creates ports on destination with IPs and MACs preserved

    Process:
     - For each port on source create port with the same IP and MAC on
       destination

    Requirements:
     - Networks and subnets must be deployed on destination
    """

    def run(self, info=None, **kwargs):

        network_resource = self.cloud.resources[utils.NETWORK_RESOURCE]
        identity_resource = self.cloud.resources[utils.IDENTITY_RESOURCE]

        info_compute = network_utils.prepare_networks(
            info,
            self.cfg.migrate.keep_ip,
            network_resource,
            identity_resource
        )

        return {
            'info': info_compute
        }
