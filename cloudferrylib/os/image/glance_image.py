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
import json
import time

from fabric.api import run
from fabric.api import settings

from cloudferrylib.base import image
from cloudferrylib.utils import file_like_proxy
from glanceclient.v1 import client as glance_client


class GlanceImage(image.Image):

    """
    The main class for working with Openstack Glance Image Service.

    """
    def __init__(self, config, cloud):
        self.config = config
        self.host = config.cloud.host
        self.cloud = cloud
        self.identity_client = cloud.resources['identity']
        self.glance_client = self.get_glance_client()
        super(GlanceImage, self).__init__(config)

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

    def get_image_by_id(self, image_id):
        for glance_image in self.get_image_list():
            if glance_image.id == image_id:
                return glance_image

    def get_image_by_name(self, image_name):
        for glance_image in self.get_image_list():
            if glance_image.name == image_name:
                return glance_image

    def get_img_id_list_by_checksum(self, checksum):
        l = []
        for glance_image in self.get_image_list():
            if glance_image.checksum == checksum:
                l.append(glance_image.id)
        return l

    def get_image(self, im):
        """ Get image by id or name. """

        for glance_image in self.get_image_list():
            if im in (glance_image.name, glance_image.id):
                return glance_image

    def get_image_status(self, image_id):
        return self.get_image_by_id(image_id).status

    def get_ref_image(self, image_id):
        return self.glance_client.images.data(image_id)._resp

    def get_image_checksum(self, image_id):
        return self.get_image_by_id(image_id).checksum

    def read_info(self, **kwargs):
        """Get info about images or specified image.

        :param image_id: Id of specified image
        :param image_name: Name of specified image
        :param images_list: List of specified images
        :param images_list_meta: Tuple of specified images with metadata in
                                 format [(image, meta)]
        :rtype: Dictionary with all necessary images info
        """

        info = {'image': {'resource': self,
                          'images': {}}}

        if kwargs.get('image_id'):
            glance_image = self.get_image_by_id(kwargs['image_id'])
            info = self.make_image_info(glance_image, info)

        elif kwargs.get('image_name'):
            glance_image = self.get_image_by_name(kwargs['image_name'])
            info = self.make_image_info(glance_image, info)

        elif kwargs.get('images_list'):
            for im in kwargs['images_list']:
                glance_image = self.get_image(im)
                info = self.make_image_info(glance_image, info)

        elif kwargs.get('images_list_meta'):
            for (im, meta) in kwargs['images_list_meta']:
                glance_image = self.get_image(im)
                info = self.make_image_info(glance_image, info)
                info['image']['images'][glance_image.id]['meta'] = meta

        else:
            for glance_image in self.get_image_list():
                info = self.make_image_info(glance_image, info)

        return info

    def make_image_info(self, glance_image, info):
        if glance_image:
            gl_image = {
                'id': glance_image.id,
                'size': glance_image.size,
                'name': glance_image.name,
                'checksum': glance_image.checksum,
                'container_format': glance_image.container_format,
                'disk_format': glance_image.disk_format,
                'is_public': glance_image.is_public,
                'protected': glance_image.protected
            }
            info['image']['images'][glance_image.id] = {'image': gl_image,
                                                        'meta': {},
                                                        }
        else:
            print 'Image has not been found'

        return info

    def deploy(self, info):
        info = copy.deepcopy(info)
        new_info = {'image': {'images': {}}}
        migrate_images_list = []
        empty_image_list = {}
        for image_id_src, gl_image in info['image']['images'].iteritems():
            if gl_image['image']:
                dst_img_checksums = {x.checksum: x for x in self.get_image_list()}
                dst_img_names = [x.name for x in self.get_image_list()]
                checksum_current = gl_image['image']['checksum']
                name_current = gl_image['image']['name']
                meta = gl_image['meta']
                if checksum_current in dst_img_checksums and (name_current + 'Migrate') in dst_img_names:
                    migrate_images_list.append((dst_img_checksums[checksum_current], meta))
                    continue
                gl_image['image']['resource_src'] = info['image']['resource']
                migrate_image = self.create_image(
                    name=gl_image['image']['name'] + 'Migrate',
                    container_format=gl_image['image']['container_format'],
                    disk_format=gl_image['image']['disk_format'],
                    is_public=gl_image['image']['is_public'],
                    protected=gl_image['image']['protected'],
                    size=gl_image['image']['size'],
                    data=file_like_proxy.FileLikeProxy(
                        gl_image['image'],
                        file_like_proxy.callback_print_progress,
                        self.config['migrate']['speed_limit']))
                migrate_images_list.append((migrate_image, meta))
            else:
                empty_image_list[image_id_src] = gl_image
        if migrate_images_list:
            im_name_list = [(im.name, meta) for (im, meta) in
                            migrate_images_list]
            new_info = self.read_info(images_list_meta=im_name_list)
        new_info['image']['images'].update(empty_image_list)
        return new_info

    def wait_for_status(self, id_res, status):
        while self.glance_client.images.get(id_res).status != status:
            time.sleep(1)

    def patch_image(self, backend_storage, image_id):
        if backend_storage == 'ceph':
            image_from_glance = self.get_image_by_id(image_id)
            with settings(host_string=self.cloud.getIpSsh()):
                out = json.loads(
                    run("rbd -p images info %s --format json" % image_id))
                image_from_glance.update(size=out["size"])
