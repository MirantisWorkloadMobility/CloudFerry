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


from cloudferry.lib.base.action import transporter
from cloudferry.lib.os.actions import get_info_objects
from cloudferry.lib.utils import utils as utl


class CopyFromObjectToObject(transporter.Transporter):
    def __init__(self, init, src_cloud, dst_cloud):
        self.src_cloud = src_cloud
        self.dst_cloud = dst_cloud
        super(CopyFromObjectToObject, self).__init__(init)

    def run(self, objstorage_info=None, **kwargs):
        dst_objstorage = self.dst_cloud.resources[utl.OBJSTORAGE_RESOURCE]
        if not objstorage_info:
            action_get_obj = get_info_objects.GetInfoObjects(self.init,
                                                             self.src_cloud)
            objstorage_info = action_get_obj.run()
        dst_objstorage.deploy(objstorage_info)
        return {}
