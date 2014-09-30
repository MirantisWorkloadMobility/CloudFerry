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


class ConvertVolumeToImage(convertor.Convertor):

    def __init__(self, disk_format, container_format=BARE):
        self.disk_format = disk_format
        self.container_format = container_format
        super(ConvertVolumeToImage, self).__init__()

    def run(self, volumes_info={}, cloud_current=None, **kwargs):
        resource_storage = cloud_current.resources['storage']
        resource_image = cloud_current.resources['image']
        images_info = dict(resource=resource_image, images=[])
        if not require_methods(['uploud_to_image'], resource_storage):
            raise RuntimeError("No require methods")
        images_from_volumes = []
        for volume in volumes_info['volumes']:
            LOG.debug("| | uploading volume %s [%s] to image service bootable=%s" %
                      (volume.display_name, volume.id, volume.bootable if hasattr(volume, 'bootable') else False))
            resp, image = resource_storage.upload_to_image(volume=volume,
                                                           force=True,
                                                           image_name=volume.id,
                                                           container_format=self.container_format,
                                                           disk_format=self.disk_format)
            image_upload = image['os-volume_upload_image']
            resource_image.wait_for_status(image_upload['image_id'], ACTIVE)
            if resource_storage.get_backend() == CEPH:
                image_from_glance = resource_image.get(image_upload['image_id'])
                with settings(host_string=cloud_current.getIpSsh()):
                    out = json.loads(run("rbd -p images info %s --format json" % image_upload['image_id']))
                    image_from_glance.update(size=out["size"])
            images_from_volumes.append({
                'image': image,
                'meta': volume
            })
        images_info['images'] = images_from_volumes
        return {
            'images_info': images_info
        }

