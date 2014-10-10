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

from cloudferrylib.base.action import convertor
from utils import utils
from fabric.api import settings
from fabric.api import run
import json
__author__ = 'mirrorcoder'

LOG = utils.get_log(__name__)
CEPH = 'ceph'
ACTIVE = 'active'
BARE = "bare"


def require_methods(methods, obj):
    for method in dir(obj):
        if method not in methods:
            return False
    return True


class ConvertorVolumeToImage(convertor.Convertor):

    def __init__(self, disk_format, cloud, container_format=BARE):
        self.cloud = cloud
        self.disk_format = disk_format
        self.container_format = container_format
        super(ConvertorVolumeToImage, self).__init__()

    def run(self, volumes_info={}, **kwargs):
        resource_storage = self.cloud.resources['storage']
        resource_image = self.cloud.resources['image']
        images_info = []
        if not require_methods(['uploud_to_image'], resource_storage):
            raise RuntimeError("No require methods")
        images_from_volumes = []
        for volume in volumes_info['volumes']:
            vol = volume['volume']
            LOG.debug("| | uploading volume %s [%s] to image service bootable=%s" %
                      (vol['display_name'], vol['id'], vol['bootable'] if hasattr(vol, 'bootable') else False))
            resp, image_id = resource_storage.upload_volume_to_image(vol['id'], force=True, image_name=vol['id'],
                                                                     container_format=self.container_format,
                                                                     disk_format=self.disk_format)
            resource_image.wait_for_status(image_id, ACTIVE)
            self.__patch_image(resource_storage.get_backend(), self.cloud, image_id)
            image_vol = resource_image.read_info({'id': image_id})
            img_new = {
                'image': image_vol,
                'meta': volume['meta']
            }
            img_new['meta']['volume'] = vol
            images_from_volumes.append(img_new)
        images_info['images'] = images_from_volumes
        return {
            'images_info': images_info
        }

    @staticmethod
    def __patch_image(backend_storage, cloud, image_id):
        resource_image = cloud.resources['image']
        if backend_storage == CEPH:
            image_from_glance = resource_image.read_info({'id': image_id})
            with settings(host_string=cloud.getIpSsh()):
                out = json.loads(run("rbd -p images info %s --format json" % image_id))
                image_from_glance.update(size=out["size"])

