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

from cloudferrylib.base.action import converter
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl

LOG = log.getLogger(__name__)
CEPH = 'ceph'
ACTIVE = 'active'
BARE = "bare"
AVAILABLE = 'available'


class ConvertImageToVolume(converter.Converter):

    def run(self, images_info=None, **kwargs):
        images_info = copy.deepcopy(images_info)
        if not images_info:
            return {}
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        resource_image = self.cloud.resources[utl.IMAGE_RESOURCE]
        volumes_info = dict(resource=resource_image, volumes=dict())
        for img in images_info[utl.IMAGES_TYPE].itervalues():
            img[utl.META_INFO][utl.IMAGE_BODY] = img[utl.IMAGE_BODY]
            vol = dict(volumes={
                img[utl.META_INFO][utl.VOLUME_BODY]['id']: dict(
                    volume=img[utl.META_INFO][utl.VOLUME_BODY],
                    meta=img[utl.META_INFO])})

            temp_instance_info = img[utl.META_INFO].pop(utl.INSTANCE_BODY)
            vol = resource_storage.deploy(vol)
            vol_new_id, vol_old_id = vol.keys()[0], vol.values()[0]
            img[utl.META_INFO][utl.INSTANCE_BODY] = temp_instance_info
            new_volume = (
                resource_storage.read_info(id=vol_new_id)[
                    utl.VOLUMES_TYPE][vol_new_id][utl.VOLUME_BODY])
            img[utl.META_INFO].pop('volume')
            volumes_info[utl.VOLUMES_TYPE][vol_new_id] = {
                'old_id': vol_old_id,
                utl.VOLUME_BODY: new_volume,
                utl.META_INFO: img[utl.META_INFO]
            }
        return {
            'storage_info': volumes_info
        }
