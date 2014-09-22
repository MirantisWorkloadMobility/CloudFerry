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

from cloudferrylib.base import Image
from glanceclient.v1 import client as glance_client

__author__ = 'asvechnikov'


class GlanceImage(Image.Image):

    """
    The main class for working with Openstack Glance Image Service.

    """
    def __init__(self, config, identity_client):
        self.config = config
        self.identity_client = identity_client
        self.glance_client = self.get_glance_client()
        super(GlanceImage, self).__init__(config)

    def get_glance_client(self):

        """ Getting glance client """

        endpoint_glance = self.identity_client.get_endpoint_by_name_service('glance')
        return glance_client.Client(endpoint=endpoint_glance,
                                    token=self.identity_client.get_auth_token_from_user())

    def get_image_list(self):
        return self.glance_client.images.list()

    def create_image(self, **kwargs):
        return self.glance_client.images.create(**kwargs)

    def delete_image(self, image_id):
        self.glance_client.images.delete(image_id)

    def get_image(self, image_id):
        for image in self.get_image_list():
            if image.id == image_id:
                return image

    def get_image_status(self, image_id):
        return self.get_image(image_id).status

    def get_ref_image(self, image_id):
        return self.get_image(image_id)._resp

    def get_image_checksum(self, image_id):
        return self.get_image(image_id).checksum