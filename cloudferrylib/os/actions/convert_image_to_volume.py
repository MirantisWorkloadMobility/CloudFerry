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


class ConvertImageToVolume(convertor.Convertor):

    def __init__(self, disk_format, container_format=BARE):
        self.disk_format = disk_format
        self.container_format = container_format
        super(ConvertImageToVolume, self).__init__()

    def run(self, volumes_info={}, cloud_current=None, **kwargs):
        resource_storage = cloud_current.resources['storage']
        resource_image = cloud_current.resources['image']
        images_info = dict(resource=resource_image, images=[])
        if not require_methods(['uploud_to_image'], resource_storage):
            raise RuntimeError("No require methods")
        volume = resource_storage.create(size=source_volume.size,
                                                    display_name=source_volume.name,
                                                    display_description=source_volume.description,
                                                    volume_type=source_volume.volume_type,
                                                    availability_zone=source_volume.availability_zone,
                                                    imageRef=image.id)
        LOG.debug("        wait for available")
        self.__wait_for_status(self.cinder_client.volumes, volume.id, 'available')
        LOG.debug("        update volume")
        self.__patch_option_bootable_of_volume(volume.id, source_volume.bootable)
        return {
            'images_info': images_info
        }

