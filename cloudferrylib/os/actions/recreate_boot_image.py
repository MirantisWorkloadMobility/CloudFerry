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
from cloudferrylib.utils import files
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils.drivers.ssh_chunks import verified_file_copy,\
    remote_md5_sum
from cloudferrylib.utils import utils
import copy
import os


LOG = utils.get_log(__name__)


class ReCreateBootImage(action.Action):

    def __init__(self, init, cloud=None):
        super(ReCreateBootImage, self).__init__(init, cloud)
        self.src_user = self.cfg.src.ssh_user
        self.dst_user = self.cfg.dst.ssh_user
        dst_password = self.cfg.dst.ssh_sudo_password
        self.dst_host = self.cfg.dst.ssh_host
        self.dst_runner = remote_runner.RemoteRunner(self.dst_host,
                                                     self.dst_user,
                                                     password=dst_password,
                                                     sudo=True)

    def run(self,
            images_info=None,
            compute_ignored_images={},
            missing_images={},
            **kwargs):
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
        images_info = copy.deepcopy(images_info)
        src_password = self.cfg.src.ssh_sudo_password
        for vm_id in missing_images:
            img_id = missing_images[vm_id]
            for image_id_src, gl_image in images_info['images'].iteritems():
                if image_id_src == img_id and not gl_image['image']:
                    diff = gl_image['meta']['instance'][0]['diff']['path_src']
                    img_src_host = \
                        gl_image['meta']['instance'][0]['diff']['host_src']
                    src_runner = remote_runner.RemoteRunner(
                        img_src_host, self.src_user, password=src_password,
                        sudo=True)

                    new_img = self.process_image(src_runner, img_id, diff)
                    gl_image['image']['id'] = new_img['id']
                    gl_image['image']['resource'] = None
                    gl_image['image']['checksum'] = new_img['checksum']
                    gl_image['image']['name'] = img_id
        return {
            'images_info': images_info,
            'compute_ignored_images': compute_ignored_images}

    def process_image(self, src_runner, img_id=None, diff=None):
        """
        Processing image file: copy from source to destination,
         create glance image
        :param img_id: image ID from source
        :param diff: diff file of root disk for instance
        :return: new image ID if image is created
        """
        with files.RemoteTempDir(src_runner) as src_tmp_dir,\
                files.RemoteTempDir(self.dst_runner) as dst_tmp_dir:
            diff_name = 'diff'
            base_name = 'base'
            diff_file = os.path.join(src_tmp_dir, diff_name)
            src_runner.run('cp {} {}'.format(diff, diff_file))
            base_file = os.path.join(src_tmp_dir, base_name)
            dst_base_file = os.path.join(dst_tmp_dir, base_name)
            qemu_img_src = self.src_cloud.qemu_img
            base = qemu_img_src.detect_backing_file(diff, src_runner.host)
            if base is not None:
                src_runner.run('cp {} {}'.format(base, base_file))
                verified_file_copy(src_runner,
                                   self.dst_runner,
                                   self.dst_user,
                                   base_file,
                                   dst_base_file,
                                   self.dst_host,
                                   1)
            else:
                verified_file_copy(src_runner,
                                   self.dst_runner,
                                   self.dst_user,
                                   diff_file,
                                   dst_base_file,
                                   self.dst_host,
                                   1)
            image_resource = self.dst_cloud.resources[utils.IMAGE_RESOURCE]
            id = image_resource.glance_img_create(img_id, 'qcow2',
                                                  dst_base_file)
            checksum = remote_md5_sum(self.dst_runner, dst_base_file)
            return {'id': id, 'checksum': checksum}
