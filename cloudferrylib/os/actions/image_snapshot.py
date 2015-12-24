# Copyright (c) 2015 Mirantis Inc.
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


from cloudferrylib.base.action import action
from cloudferrylib.utils import log
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)

NAMESPACE = 'IMAGE_SNAPSHOT'


class ImageSnapshotBasic(action.Action):

    """Base class that contains common to image_snapshot methods"""

    def get_image_resource(self):
        """returns cloudferry image resource"""
        return self.cloud.resources[utils.IMAGE_RESOURCE]

    def get_images_id_list(self):
        """returns array of images id"""
        return self.get_image_resource().read_info()['images'].keys()


class ImageSnapshot(ImageSnapshotBasic):
    def run(self, *args, **kwargs):
        LOG.info("Creation of images snapshot")
        return {NAMESPACE: self.get_images_id_list()}


class ImageRollback(ImageSnapshotBasic):
    def run(self, *args, **kwargs):
        id_from_namespace = kwargs.get(NAMESPACE, [])
        current_id = self.get_images_id_list()
        image = self.get_image_resource()
        for image_id in current_id:
            if image_id not in id_from_namespace:
                image.delete_image(image_id)
