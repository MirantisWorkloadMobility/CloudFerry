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
"""Migration of objects from SRC to DST clouds."""


from cloudferrylib.utils import utils


CLOUD = 'cloud'
SRC, DST = 'src', 'dst'


class Migration(object):

    """ Map SRC objects to corresponding DST objects they migrated to."""

    def __init__(self, src_cloud, dst_cloud, resource):
        self.cloud = {
            SRC: src_cloud,
            DST: dst_cloud,
        }
        self.obj_map = {}

        if resource not in utils.RESOURCE_TYPES:
            raise NotImplementedError('Unknown resource: %s', resource)
        self.default_resource_type = utils.RESOURCE_TYPES[resource]

        self.resource = {
            SRC: self.cloud[SRC].resources.get(resource),
            DST: self.cloud[DST].resources.get(resource),
        }

    def get_default(self, resource_type):
        """ Get default ID by `resource_type` or None.

        :return: str
        """
        if resource_type in (utils.TENANTS_TYPE, utils.USERS_TYPE):
            return self.resource[DST].get_default_id(resource_type)

    def map_migrated_objects(self, resource_type=None):
        """Build map SRC -> DST object IDs.

        :return: dict

        """

        if not resource_type:
            resource_type = self.default_resource_type

        objs = {
            pos: self.read_objects(pos, resource_type)
            for pos in (SRC, DST)
        }

        # objects -> object
        body = resource_type[:-1]

        obj_map = dict(
            [(src[body]['id'], dst[body]['id'])
             for src in objs[SRC] for dst in objs[DST]
             if self.obj_identical(src[body], dst[body])])
        return obj_map

    def migrated_id(self, src_object_id, resource_type=None):
        """ Get migrated object ID by SRC object ID.

        :return: DST object ID

        """
        if not resource_type:
            resource_type = self.default_resource_type

        if resource_type not in self.obj_map:
            self.obj_map[resource_type] = \
                self.map_migrated_objects(resource_type)

        return self.obj_map[resource_type].get(src_object_id,
                                               self.get_default(resource_type))

    def identical(self, src_id, dst_id, resource_type=None):
        """ Check if SRC object with `src_id` === DST object with `dst_id`.

        :return: boolean

        """
        if not resource_type:
            resource_type = self.default_resource_type
        return dst_id == self.migrated_id(src_id, resource_type=resource_type)

    def obj_identical(self, src_obj, dst_obj):
        """Compare src and dst objects from resource info.

        :return: boolean

        """

        dst_res = self.resource[DST]
        return dst_res.identical(src_obj, dst_obj)

    def read_objects(self, position, resource_type):
        """Read objects info from `position` cloud.

        :return: list

        """
        res = self.resource[position]
        objs = res.read_info()[resource_type]
        return objs.values() if isinstance(objs, dict) else objs
