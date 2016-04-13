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
from cloudferry.lib.utils import utils as utl


class GetInfoObjects(action.Action):
    def __init__(self, init, cloud=None):
        super(GetInfoObjects, self).__init__(init, cloud)

    def run(self, **kwargs):
        """Get info about objects from cloud object storage."""

        objstorage_resource = self.cloud.resources[utl.OBJSTORAGE_RESOURCE]
        objstorage_info = objstorage_resource.read_info()
        return {'objstorage_info': objstorage_info}
