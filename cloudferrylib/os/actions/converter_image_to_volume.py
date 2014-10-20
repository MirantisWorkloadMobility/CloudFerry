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
from cloudferrylib.utils import utils as utl
__author__ = 'mirrorcoder'

LOG = utl.get_log(__name__)
CEPH = 'ceph'
ACTIVE = 'active'
BARE = "bare"
AVAILABLE = 'available'


class ConverterImageToVolume(converter.Converter):

    def __init__(self):
        super(ConverterImageToVolume, self).__init__()

    def run(self, images_info={}, cloud_current=None, **kwargs):
        resource_storage = cloud_current.resources[utl.STORAGE_RESOURCE]
        resource_image = cloud_current.resources[utl.IMAGE_RESOURCE]
        volumes_info = dict(resource=resource_image, storage=dict(volumes=list()))
        for img in images_info[utl.IMAGE_RESOURCE][utl.IMAGES_TYPE]:
            img[utl.META_INFO][utl.IMAGE_BODY] = img[utl.IMAGE_BODY]
            vol = dict(storage=dict(volumes=[
                dict(volume=img[utl.META_INFO][utl.VOLUME_BODY], meta=img[utl.META_INFO])]))
            volume = resource_storage.deploy(vol)[0]
            volume = resource_storage \
                .read_info(id=volume.id)[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][0][utl.VOLUME_BODY]
            volumes_info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE].append({
                utl.VOLUME_BODY: volume,
                utl.META_INFO: img[utl.META_INFO]
            })
        return {
            'volumes_info': volumes_info
        }

