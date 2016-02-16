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
from cloudferrylib.base import exception
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)


def get_boot_volume(instance):
    return instance[utl.INSTANCE_BODY]['boot_volume']


def get_image_id_from_volume(volume, storage):
    volumes = storage.read_info(id=volume['id'])[utl.VOLUMES_TYPE]
    volume_details = volumes[volume['id']][utl.VOLUME_BODY]
    return volume_details['volume_image_metadata']['image_id']


class ConvertComputeToImage(action.Action):

    def __init__(self, init, cloud=None, target_output='images_info'):
        super(ConvertComputeToImage, self).__init__(init, cloud)
        self.target_output = target_output

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        image_info = {utl.IMAGES_TYPE: {}}
        images_body = image_info[utl.IMAGES_TYPE]
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        dst_image_resource = self.dst_cloud.resources[utl.IMAGE_RESOURCE]
        storage_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        compute_ignored_images = {}
        missing_images = {}
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            _instance = instance[utl.INSTANCE_BODY]
            image_id = None
            if _instance['boot_mode'] == utl.BOOT_FROM_VOLUME:
                if _instance['volumes']:
                    volume = get_boot_volume(instance)
                    image_id = get_image_id_from_volume(volume,
                                                        storage_resource)
            else:
                image_id = _instance['image_id']
            # TODO: Case when image is None
            if image_id and not dst_image_resource.image_exists(image_id):
                if image_id in images_body:
                    images_body[image_id][utl.META_INFO][
                        utl.INSTANCE_BODY].append(instance)
                else:
                    images_body[image_id] = {utl.IMAGE_BODY: {},
                                             utl.META_INFO: {
                                             utl.INSTANCE_BODY: [instance]}}
                    try:
                        image_resource.get_ref_image(image_id)
                    except exception.ImageDownloadError:
                        missing_images[instance_id] = image_id
                        continue
                    img = image_resource.get_image_by_id_converted(image_id)
                    img = img[utl.IMAGES_TYPE]
                    if img:
                        images_body.update(img)
                        images_body[image_id][utl.META_INFO][
                            utl.INSTANCE_BODY] = [instance]
                    else:
                        LOG.warning("No boot image for instance, "
                                    "need to re-create it")
                        missing_images[instance_id] = image_id
            else:
                compute_ignored_images[instance_id] = instance
        if missing_images:
            LOG.warning('List of broken images: %s', missing_images.values())
        return {
            self.target_output: image_info,
            'compute_ignored_images': compute_ignored_images,
            'missing_images': missing_images
        }
