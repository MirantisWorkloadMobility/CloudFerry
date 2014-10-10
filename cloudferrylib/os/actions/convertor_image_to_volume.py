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
AVAILABLE = 'available'


def require_methods(methods, obj):
    for method in dir(obj):
        if method not in methods:
            return False
    return True


class ConvertorImageToVolume(convertor.Convertor):

    def __init__(self):
        super(ConvertorImageToVolume, self).__init__()

    def run(self, images_info={}, cloud_current=None, **kwargs):
        resource_storage = cloud_current.resources['storage']
        resource_image = cloud_current.resources['image']
        volumes_info = dict(resource=resource_image, volumes=[])
        if not require_methods(['uploud_to_image'], resource_storage):
            raise RuntimeError("No require methods")
        for vol in images_info:
            volume = resource_storage.create(size=vol['meta'].size,
                                             display_name=vol['meta'].name,
                                             display_description=vol['meta'].description,
                                             volume_type=vol['meta'].volume_type,
                                             availability_zone=vol['meta'].availability_zone,
                                             imageRef=vol['image'].image_id)
            LOG.debug("        wait for available")
            resource_storage.wait_for_status(volume.id, AVAILABLE)
            LOG.debug("        update volume")
            resource_storage.finish(volume.id, vol['meta'])
            volumes_info['volumes'].append({
                'volume': volume,
                'meta': {
                    'image': vol
                }
            })
        return {
            'volumes_info': volumes_info
        }

