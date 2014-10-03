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

from cloudferrylib.base import image
from glanceclient.v1 import client as glance_client

from migrationlib.os.utils import FileLikeProxy


class GlanceImage(image.Image):

    """
    The main class for working with Openstack Glance Image Service.

    """
    def __init__(self, config, identity_client):
        self.config = config
        self.identity_client = identity_client
        self.glance_client = self.get_glance_client()
        super(GlanceImage, self).__init__()

    def get_glance_client(self):

        """ Getting glance client """

        endpoint_glance = self.identity_client.get_endpoint_by_service_name(
            'glance')
        return glance_client.Client(
            endpoint=endpoint_glance,
            token=self.identity_client.get_auth_token_from_user())

    def get_image_list(self):
        return self.glance_client.images.list()

    def create_image(self, **kwargs):
        return self.glance_client.images.create(**kwargs)

    def delete_image(self, image_id):
        self.glance_client.images.delete(image_id)

    def get_image(self, image_id):
        for glance_image in self.get_image_list():
            if glance_image.id == image_id:
                return glance_image

    def get_image_status(self, image_id):
        return self.get_image(image_id).status

    def get_ref_image(self, image_id):
        return self.glance_client.images.data(image_id)._resp

    def get_image_checksum(self, image_id):
        return self.get_image(image_id).checksum

    def read_info(self):
        info = {'images': self.get_image_list(),
                'resource': self}

        return info

    def deploy(self, info):
        migrate_images_list = []
        for gl_image in info['images']:
            if gl_image.name + 'Migrate' in [x.name for x in
                                             self.get_image_list()]:
                continue
            gl_image.resource_src = info['resource']
            migrate_image = self.create_image(
                name=gl_image.name + 'Migrate',
                container_format=gl_image.container_format,
                disk_format=gl_image.disk_format,
                is_public=gl_image.is_public,
                protected=gl_image.protected,
                size=gl_image.size,
                data=FileLikeProxy.FileLikeProxy(
                    gl_image,
                    FileLikeProxy.callback_print_progress,
                    self.config['speed_limit']))

            migrate_images_list.append(migrate_image)

        return migrate_images_list
