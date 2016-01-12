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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils
from cloudferrylib.utils import log


LOG = log.getLogger(__name__)


def get_object_name_from_resource(resource_name):
    resource_to_object_name_map = {
        utils.INSTANCES_TYPE: "instance",
        utils.VOLUMES_TYPE: "volume",
        utils.NETWORKS_TYPE: "network",
        utils.IMAGES_TYPE: "image",
        utils.TENANTS_TYPE: "tenant",
        utils.USERS_TYPE: "user",
    }

    return resource_to_object_name_map.get(resource_name, "UNKNOWN OBJECT")


class MigrationProgressView(object):
    """Presents information about object migration process to user"""

    def __init__(self, obj_type, output=LOG):
        self.type = obj_type
        self.num = 0
        self.total = 0
        self.first_time = True
        self.log = output

    def show_progress(self, current_object, all_objects):
        if self.first_time:
            self.first_time = False

            # one object has been already popped off all_objects
            # super lame, but still better than messing with GetInfoIter
            self.total = len(all_objects) + 1

        self.num += 1

        message = ("Starting migration of %(object_type)s '%(name_or_id)s', "
                   "%(num)d of %(total)d, %(percentage).0f%%")
        name_or_id = self._get_obj_name(current_object)

        self.log.info(message, {"object_type": self.type,
                                "name_or_id": name_or_id,
                                "num": self.num,
                                "total": self.total,
                                "percentage": 100.0 * self.num / self.total})

    def _get_obj_name(self, current_object):
        obj_info = current_object.get(self.type, {})
        default_name = "NAME OR ID NOT FOUND"
        return obj_info.get('name') or obj_info.get('id') or default_name


class GetInfoIter(action.Action):

    def __init__(self, init, iter_info_name='info_iter', info_name='info',
                 resource_name=utils.INSTANCES_TYPE):
        self.iter_info_name = iter_info_name
        self.info_name = info_name
        self.resource_name = resource_name

        self.view = MigrationProgressView(
                obj_type=get_object_name_from_resource(resource_name))

        super(GetInfoIter, self).__init__(init)

    def run(self, **kwargs):
        info = kwargs[self.iter_info_name]
        objs = info[self.resource_name]
        obj_id = objs.keys()[0]
        obj = objs.pop(obj_id)
        new_info = {
            self.resource_name: {obj_id: obj}
        }

        self.view.show_progress(obj, objs)

        return {
            self.iter_info_name: info,
            self.info_name: new_info
        }
