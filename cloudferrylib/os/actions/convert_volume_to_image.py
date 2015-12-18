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


from cloudferrylib.base.action import converter
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl

import copy

LOG = log.getLogger(__name__)
CEPH = 'ceph'
ACTIVE = 'active'
BARE = "bare"


def require_methods(methods, obj):
    for method in methods:
        if method not in dir(obj):
            return False
    return True


class ConvertVolumeToImage(converter.Converter):

    def run(self, storage_info={}, **kwargs):
        self.disk_format = self.cfg.migrate.disk_format
        self.container_format = self.cfg.migrate.container_format
        volumes_info = copy.deepcopy(storage_info)
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        resource_image = self.cloud.resources[utl.IMAGE_RESOURCE]
        images_info = {}
        if not require_methods(['upload_volume_to_image'], resource_storage):
            raise RuntimeError("No require methods")
        images_from_volumes = {}
        for volume_id, volume in volumes_info[utl.VOLUMES_TYPE].iteritems():
            vol = volume['volume']
            LOG.debug(
                "| | uploading volume %s [%s] to image service bootable=%s" % (
                    vol['display_name'], vol['id'],
                    vol['bootable'] if hasattr(vol, 'bootable') else False))
            resp, image_id = resource_storage.upload_volume_to_image(
                vol['id'], force=True, image_name=vol['id'],
                container_format=self.container_format,
                disk_format=self.disk_format)
            resource_image.wait_for_status(image_id,
                                           resource_image.get_status,
                                           ACTIVE)
            resource_image.patch_image(resource_image.get_backend(), image_id)
            image_vol = resource_image.get_image_by_id_converted(image_id)
            img_new = {
                utl.IMAGE_BODY: (
                    image_vol[utl.IMAGES_TYPE][image_id][utl.IMAGE_BODY]),
                utl.META_INFO: volume[utl.META_INFO]
            }
            img_new[utl.META_INFO][utl.VOLUME_BODY] = vol
            images_from_volumes[image_id] = img_new
        images_info[utl.IMAGES_TYPE] = images_from_volumes
        return {
            'images_info': images_info
        }
