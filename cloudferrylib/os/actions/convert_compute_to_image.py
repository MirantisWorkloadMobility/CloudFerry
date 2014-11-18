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


def get_boot_volume(instance):
    return instance[utl.INSTANCE_BODY]['volumes'][0]


def get_image_id_from_volume(volume, storage):
    volumes = storage.read_info(id=volume['id'])[utl.STORAGE_RESOURCE][
        utl.VOLUMES_TYPE]
    volume_details = volumes[volume['id']][utl.VOLUME_BODY]
    return volume_details['volume_image_metadata']['image_id']


class ConvertComputeToImage(action.Action):

    def __init__(self, cfg=None, cloud=None):
        self.cfg = cfg
        self.cloud = cloud
        super(ConvertComputeToImage, self).__init__()

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        image_info = {utl.IMAGE_RESOURCE: {utl.IMAGES_TYPE: {}}}
        images_body = image_info[utl.IMAGE_RESOURCE][utl.IMAGES_TYPE]
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        storage_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        image_info[utl.IMAGE_RESOURCE]['resource'] = image_resource
        for instance in info[utl.COMPUTE_RESOURCE][
                utl.INSTANCES_TYPE].itervalues():
            _instance = instance[utl.INSTANCE_BODY]
            if _instance['image_id'] is None:
                if _instance['volumes']:
                    volume = get_boot_volume(instance)
                    image_id = get_image_id_from_volume(volume,
                                                        storage_resource)
            else:
                image_id = _instance['image_id']
            img = image_resource.read_info(image_id=image_id)
            img = img[utl.IMAGE_RESOURCE][utl.IMAGES_TYPE]
            images_body[image_id] = {utl.IMAGE_BODY: {}, utl.META_INFO: {
                utl.INSTANCE_BODY: instance
            }}
            if img:
                images_body.update(img)
                images_body[image_id][utl.META_INFO][
                    utl.INSTANCE_BODY] = instance
        return {'images_info': image_info}
