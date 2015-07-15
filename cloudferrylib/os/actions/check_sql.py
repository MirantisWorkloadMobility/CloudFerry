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
from cloudferrylib.utils import utils


class CheckSQL(action.Action):

    def run(self, info=None, **kwargs):
        SQL = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES LIMIT 1"

        nova = self.cloud.resources[utils.COMPUTE_RESOURCE]
        nova.mysql_connector.execute(SQL)

        cinder = self.cloud.resources[utils.STORAGE_RESOURCE]
        cinder.mysql_connector.execute(SQL)

        glance = self.cloud.resources[utils.IMAGE_RESOURCE]
        glance.mysql_connector.execute(SQL)
