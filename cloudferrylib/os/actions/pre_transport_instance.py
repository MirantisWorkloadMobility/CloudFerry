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

from fabric.api import env
from fabric.api import run
from fabric.api import settings

from cloudferrylib.base.action import action
from cloudferrylib.os.actions import convert_file_to_image
from cloudferrylib.os.actions import convert_image_to_file
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils import utils as utl, forward_agent

from cloudferrylib.utils.drivers import ssh_ceph_to_ceph
from cloudferrylib.utils.drivers import ssh_ceph_to_file
from cloudferrylib.utils.drivers import ssh_file_to_file
from cloudferrylib.utils.drivers import ssh_file_to_ceph


CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
ISCSI = 'iscsi'
COMPUTE = 'compute'
INSTANCES = 'instances'
INSTANCE_BODY = 'instance'
INSTANCE = 'instance'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
DIFF_OLD = 'diff_old'
EPHEMERAL_OLD = 'ephemeral_old'

PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
HOST_SRC = 'host_src'

TEMP = 'temp'
FLAVORS = 'flavors'


TRANSPORTER_MAP = {CEPH: {CEPH: ssh_ceph_to_ceph.SSHCephToCeph,
                          ISCSI: ssh_ceph_to_file.SSHCephToFile},
                   ISCSI: {CEPH: ssh_file_to_ceph.SSHFileToCeph,
                           ISCSI: ssh_file_to_file.SSHFileToFile}}


class PreTransportInstance(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        # Init before run
        src_compute = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        dst_compute = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        backend_ephem_drv_src = src_compute.config.compute.backend
        backend_ephem_drv_dst = dst_compute.config.compute.backend
        new_info = {
            utl.INSTANCES_TYPE: {
            }
        }

        # Get next one instance
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            instance_boot = instance[utl.INSTANCE_BODY]['boot_mode']
            one_instance = {
                utl.INSTANCES_TYPE: {
                    instance_id: instance
                }
            }
            # Pre processing deploy
            if ((instance_boot == utl.BOOT_FROM_IMAGE) and
                    (backend_ephem_drv_src == CEPH)):
                self.transport_image(self.dst_cloud, one_instance, instance_id)
            if ((instance_boot == utl.BOOT_FROM_IMAGE) and
                    (backend_ephem_drv_src == ISCSI) and
                    (backend_ephem_drv_dst == CEPH)):
                self.transport_diff_and_merge(self.dst_cloud,
                                              one_instance,
                                              instance_id)
            new_info[utl.INSTANCES_TYPE].update(
                one_instance[utl.INSTANCES_TYPE])

        return {
            'info': new_info
        }

    def convert_file_to_image(self,
                              dst_cloud,
                              base_file,
                              disk_format,
                              instance_id):
        converter = convert_file_to_image.ConvertFileToImage(self.init,
                                                             cloud=dst_cloud)
        dst_image_id = converter.run(file_path=base_file,
                                     image_format=disk_format,
                                     image_name="%s-image" % instance_id)
        return dst_image_id

    def convert_image_to_file(self, cloud, image_id, filename):
        convertor = convert_image_to_file.ConvertImageToFile(self.init,
                                                             cloud=cloud)
        convertor.run(image_id=image_id,
                      base_filename=filename)

    def merge_file(self, cloud, base_file, diff_file):
        host = cloud.cloud_config.cloud.host
        self.rebase_diff_file(host, base_file, diff_file)
        self.commit_diff_file(host, diff_file)

    def transport_image(self, dst_cloud, info, instance_id):
        path_dst = "%s/%s" % (dst_cloud.cloud_config.cloud.temp,
                              "temp%s_base" % instance_id)
        info[INSTANCES][instance_id][DIFF][PATH_DST] = path_dst
        info[INSTANCES][instance_id][DIFF][HOST_DST] = dst_cloud.getIpSsh()

        transporter = task_transfer.TaskTransfer(
            self.init,
            TRANSPORTER_MAP[CEPH][ISCSI],
            resource_name=utl.INSTANCES_TYPE,
            resource_root_name=utl.DIFF_BODY)
        transporter.run(info=info)

        converter = convert_file_to_image.ConvertFileToImage(self.init,
                                                             'dst_cloud')

        dst_image_id = converter.run(file_path=path_dst,
                                     image_format='raw',
                                     image_name="%s-image" % instance_id)
        info[INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = dst_image_id

    def transport_diff_and_merge(self, dst_cloud, info, instance_id):
        convertor = convert_image_to_file.ConvertImageToFile(self.init,
                                                             cloud='dst_cloud')
        transporter = task_transfer.TaskTransfer(
            self.init,
            TRANSPORTER_MAP[ISCSI][ISCSI],
            resource_name=utl.INSTANCES_TYPE,
            resource_root_name=utl.DIFF_BODY)
        image_id = info[INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id']

        base_file = "%s/%s" % (dst_cloud.cloud_config.cloud.temp,
                               "temp%s_base" % instance_id)
        diff_file = "%s/%s" % (dst_cloud.cloud_config.cloud.temp,
                               "temp%s" % instance_id)

        info[INSTANCES][instance_id][DIFF][PATH_DST] = diff_file
        info[INSTANCES][instance_id][DIFF][HOST_DST] = dst_cloud.getIpSsh()

        convertor.run(image_id=image_id,
                      base_filename=base_file)

        transporter.run(info=info)

        self.merge_file(dst_cloud, base_file, diff_file)

        image_res = dst_cloud.resources[utl.IMAGE_RESOURCE]
        images = image_res.get_image_by_id_converted(image_id=image_id)
        image = images[utl.IMAGE_RESOURCE][utl.IMAGES_TYPE][image_id]
        disk_format = image[utl.IMAGE_BODY]['disk_format']
        if image_res.config.image.convert_to_raw:
            if disk_format.lower() != utl.RAW:
                self.convert_file_to_raw(dst_cloud.cloud_config.cloud.host,
                                         disk_format,
                                         base_file)
                disk_format = utl.RAW
        converter = convert_file_to_image.ConvertFileToImage(self.init,
                                                             cloud='dst_cloud')
        dst_image_id = converter.run(file_path=base_file,
                                     image_format=disk_format,
                                     image_name="%s-image" % instance_id)
        info[INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = dst_image_id

    @staticmethod
    def convert_file_to_raw(host, disk_format, filepath):
        with settings(host_string=host,
                      connection_attempts=env.connection_attempts):
            with forward_agent(env.key_filename):
                run("qemu-img convert -f %s -O raw %s %s.tmp" %
                    (disk_format, filepath, filepath))
                run("mv -f %s.tmp %s" % (filepath, filepath))

    @staticmethod
    def rebase_diff_file(host, base_file, diff_file):
        cmd = "qemu-img rebase -u -b %s %s" % (base_file, diff_file)
        with settings(host_string=host,
                      connection_attempts=env.connection_attempts):
            run(cmd)

    @staticmethod
    def commit_diff_file(host, diff_file):
        with settings(host_string=host,
                      connection_attempts=env.connection_attempts):
            run("qemu-img commit %s" % diff_file)
