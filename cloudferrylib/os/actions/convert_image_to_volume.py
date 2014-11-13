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

LOG = utl.get_log(__name__)
CEPH = 'ceph'
ACTIVE = 'active'
BARE = "bare"
AVAILABLE = 'available'


class ConvertImageToVolume(converter.Converter):

    def __init__(self, cloud):
        self.cloud = cloud
        super(ConvertImageToVolume, self).__init__()

    def run(self, images_info=None, **kwargs):
        if not images_info:
            return {}
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        resource_image = self.cloud.resources[utl.IMAGE_RESOURCE]
        volumes_info = dict(resource=resource_image, storage=dict(volumes={}))
        for img in images_info[utl.IMAGE_RESOURCE][
                utl.IMAGES_TYPE].itervalues():
            img[utl.META_INFO][utl.IMAGE_BODY] = img[utl.IMAGE_BODY]
            vol = dict(storage=dict(volumes={
                img[utl.META_INFO][utl.VOLUME_BODY]['id']: dict(
                    volume=img[utl.META_INFO][utl.VOLUME_BODY],
                    meta=img[utl.META_INFO])}))
            volume = resource_storage.deploy(vol)[0]
            new_volume = (
                resource_storage.read_info(id=volume.id)[utl.STORAGE_RESOURCE][
                    utl.VOLUMES_TYPE][volume.id][utl.VOLUME_BODY])
            img[utl.META_INFO].pop('volume')
            volumes_info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][volume.id] = {
                utl.VOLUME_BODY: new_volume,
                utl.META_INFO: img[utl.META_INFO]
            }
        return {
            'volumes_info': volumes_info
        }
