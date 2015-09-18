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


import copy

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class CleanupImages(action.Action):

    def run(self, info, **kwargs):
        info = copy.deepcopy(info)

        src_img = self.src_cloud.resources[utl.IMAGE_RESOURCE]
        dst_img = self.dst_cloud.resources[utl.IMAGE_RESOURCE]

        checksum_list = []

        for instance in info[utl.INSTANCES_TYPE].itervalues():
            volumes = instance[utl.META_INFO].get(utl.VOLUME_BODY)

            if not volumes:
                continue

            for vol in volumes:
                if utl.IMAGE_BODY in vol[utl.META_INFO]:
                    image_checksum = \
                        vol[utl.META_INFO][utl.IMAGE_BODY]['checksum']

                    if image_checksum not in checksum_list:
                        checksum_list.append(image_checksum)

        for chs in checksum_list:
            map(src_img.delete_image, src_img.get_img_id_list_by_checksum(chs))
            map(dst_img.delete_image, dst_img.get_img_id_list_by_checksum(chs))

        return {}
