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

import logging

from cloudferrylib.base.action import action
from cloudferrylib.copy_engines import bbcp_copier

LOG = logging.getLogger(__name__)


class RemoveBBCP(action.Action):
    """
    Action removes the copied bbcp from remote hosts. Should be called at end
    of the migration.
    """
    def run(self, **kwargs):
        bbcp_copier.remove_bbcp(self.src_cloud)
        bbcp_copier.remove_bbcp(self.dst_cloud)
