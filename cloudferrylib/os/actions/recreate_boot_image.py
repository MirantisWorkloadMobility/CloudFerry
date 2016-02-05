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

import logging

from cloudferrylib.base.action import action
from cloudferrylib.utils import files
from cloudferrylib.utils import file_proxy
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import utils

LOG = logging.getLogger(__name__)


class ReCreateBootImage(action.Action):

    def run(self, images_info, compute_ignored_images=None,
            missing_images=None, **kwargs):
        """
        Create boot image on destination based on root disk of instance.
        Use diff&base images, commit all changes from diff to base,
        copy base and add as a glance image.
        Image ID from source is used as a name of new image because we can't
        get name of deleted image.

        :param images_info: dict with all images on source
        :param compute_ignored_images: not used, just resending to down level
        :param missing_images: dict with images that has been removed on source
        :param kwargs: not used
        :return: images_info and compute_ignored_images
        """
        if missing_images:
            images_info['images'] = self.process_images(images_info['images'],
                                                        missing_images)
        return {'images_info': images_info,
                'compute_ignored_images': compute_ignored_images or {}}

    def process_images(self, images, missing_images):
        for image_id in set(missing_images.values()):
            image = images[image_id]['image']
            if not image:
                diff = images[image_id]['meta']['instance'][0]['diff']
                new_image = self.restore_image(image_id, diff['host_src'],
                                               diff['path_src'])
                image['id'] = new_image.id
                image['resource'] = None
                image['checksum'] = new_image.checksum
                image['name'] = new_image.name
                image['size'] = new_image.size
        return images

    def restore_image(self, image_id, host, filename):
        """
        Processing image file: copy from source to destination,
        create glance image

        :param image_id: image ID from source
        :param image_host: host of image from source
        :param diff: diff file of root disk for instance
        :return: new image if image is created
        """
        LOG.debug('Processing an image %s from host %s and filename %s',
                  image_id, host, filename)

        image_file_info = self.src_cloud.qemu_img.get_info(filename, host)
        image_resource = self.dst_cloud.resources[utils.IMAGE_RESOURCE]
        runner = remote_runner.RemoteRunner(host,
                                            self.cfg.src.ssh_user,
                                            self.cfg.src.ssh_sudo_password,
                                            True)
        file_size = files.remote_file_size(runner, filename)
        with files.RemoteStdout(
                host, self.cfg.src.ssh_user,
                'dd if={filename}',
                filename=image_file_info.backing_filename) as f:
            fp = file_proxy.FileProxy(f.stdout,
                                      name='image %s' % image_id,
                                      size=file_size)
            new_image = image_resource.create_image(
                id=image_id,
                name='restored image %s from host %s' % (image_id,
                                                         host),
                container_format='bare',
                disk_format=image_file_info.format,
                is_public=True,
                data=fp)
            return new_image
