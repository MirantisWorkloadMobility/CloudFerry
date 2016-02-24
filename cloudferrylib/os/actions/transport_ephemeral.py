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
import hashlib
import os

from fabric.api import env
from fabric.api import run
from fabric.api import settings
from oslo_config import cfg

from cloudferrylib.base.action import action
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils.utils import forward_agent
from cloudferrylib.utils import utils as utl
from cloudferrylib.utils import qemu_img as qemu_img_util

CONF = cfg.CONF

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
BACKING_FILE_DST = 'backing_file_dst'

TEMP = 'temp'
FLAVORS = 'flavors'

TRANSPORTER_MAP = {CEPH: {CEPH: 'SSHCephToCeph',
                          ISCSI: 'SSHCephToFile'},
                   ISCSI: {CEPH: 'SSHFileToCeph',
                           ISCSI: 'SSHFileToFile'}}


class TransportEphemeral(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        # Init before run
        new_info = {
            utl.INSTANCES_TYPE: {
            }
        }

        # Get next one instance
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            is_ephemeral = instance[utl.INSTANCE_BODY]['is_ephemeral']
            one_instance = {
                utl.INSTANCES_TYPE: {
                    instance_id: instance
                }
            }
            if is_ephemeral:
                self.copy_ephemeral(self.src_cloud,
                                    self.dst_cloud,
                                    one_instance)
            new_info[utl.INSTANCES_TYPE].update(
                one_instance[utl.INSTANCES_TYPE])

        return {
            'info': new_info
        }

    @staticmethod
    def delete_remote_file_on_compute(path_file, host_cloud,
                                      host_instance):
        with settings(host_string=host_cloud,
                      connection_attempts=env.connection_attempts):
            with forward_agent(env.key_filename):
                run("ssh -oStrictHostKeyChecking=no %s  'rm -rf %s'" %
                    (host_instance, path_file))

    def copy_data_via_ssh(self, src_cloud, dst_cloud, info, body, resources,
                          types):
        dst_storage = dst_cloud.resources[resources]
        src_compute = src_cloud.resources[resources]
        src_backend = src_compute.config.compute.backend
        dst_backend = dst_storage.config.compute.backend
        ssh_driver = (CONF.migrate.copy_backend
                      if CONF.migrate.direct_compute_transfer
                      else TRANSPORTER_MAP[src_backend][dst_backend])
        transporter = task_transfer.TaskTransfer(
            self.init,
            ssh_driver,
            resource_name=types,
            resource_root_name=body)
        transporter.run(info=info)

    def copy_ephemeral(self, src_cloud, dst_cloud, info):
        dst_storage = dst_cloud.resources[utl.COMPUTE_RESOURCE]
        src_compute = src_cloud.resources[utl.COMPUTE_RESOURCE]
        src_backend = src_compute.config.compute.backend
        dst_backend = dst_storage.config.compute.backend
        if (src_backend == CEPH) and (dst_backend == ISCSI):
            self.copy_ephemeral_ceph_to_iscsi(src_cloud, dst_cloud, info)
        elif (src_backend == ISCSI) and (dst_backend == CEPH):
            self.copy_ephemeral_iscsi_to_ceph(src_cloud, info)
        else:
            self.copy_data_via_ssh(src_cloud,
                                   dst_cloud,
                                   info,
                                   utl.EPHEMERAL_BODY,
                                   utl.COMPUTE_RESOURCE,
                                   utl.INSTANCES_TYPE)
            self.rebase_diff(dst_cloud, info)

    def copy_ephemeral_ceph_to_iscsi(self, src_cloud, dst_cloud, info):
        transporter = task_transfer.TaskTransfer(
            self.init,
            TRANSPORTER_MAP[ISCSI][ISCSI],
            resource_name=utl.INSTANCES_TYPE,
            resource_root_name=utl.EPHEMERAL_BODY)

        instances = info[utl.INSTANCES_TYPE]
        temp_src = src_cloud.cloud_config.cloud.temp
        host_dst = dst_cloud.cloud_config.cloud.ssh_host
        qemu_img_dst = dst_cloud.qemu_img
        qemu_img_src = src_cloud.qemu_img

        temp_path_src = temp_src + "/%s" + utl.DISK_EPHEM
        for inst_id, inst in instances.iteritems():

            path_src_id_temp = temp_path_src % inst_id
            host_compute_dst = inst[EPHEMERAL][HOST_DST]
            inst[EPHEMERAL][
                BACKING_FILE_DST] = qemu_img_dst.detect_backing_file(
                inst[EPHEMERAL][PATH_DST], host_compute_dst)
            self.delete_remote_file_on_compute(inst[EPHEMERAL][PATH_DST],
                                               host_dst,
                                               host_compute_dst)
            qemu_img_src.convert(
                utl.QCOW2,
                'rbd:%s' % inst[EPHEMERAL][PATH_SRC], path_src_id_temp)
            inst[EPHEMERAL][PATH_SRC] = path_src_id_temp

        transporter.run(info=info)

        for inst_id, inst in instances.iteritems():
            host_compute_dst = inst[EPHEMERAL][HOST_DST]
            qemu_img_dst.diff_rebase(inst[EPHEMERAL][BACKING_FILE_DST],
                                     inst[EPHEMERAL][PATH_DST],
                                     host_compute_dst)

    def copy_ephemeral_iscsi_to_ceph(self, src_cloud, info):
        instances = info[utl.INSTANCES_TYPE]
        qemu_img_src = src_cloud.qemu_img
        transporter = task_transfer.TaskTransfer(
            self.init,
            TRANSPORTER_MAP[ISCSI][CEPH],
            resource_name=utl.INSTANCES_TYPE,
            resource_root_name=utl.EPHEMERAL_BODY)

        for inst_id, inst in instances.iteritems():
            path_src = inst[EPHEMERAL][PATH_SRC]
            path_src_temp_raw = path_src + "." + utl.RAW

            host_src = inst[EPHEMERAL][HOST_SRC]
            qemu_img_src.convert(utl.RAW,
                                 path_src,
                                 path_src_temp_raw,
                                 host_src)
            inst[EPHEMERAL][PATH_SRC] = path_src_temp_raw

        transporter.run(info=info)

    @staticmethod
    def rebase_diff(dst_cloud, info):
        for instance_id, obj in info[utl.INSTANCES_TYPE].items():
            image_id = obj['instance']['image_id']
            new_backing_file = hashlib.sha1(image_id).hexdigest()
            diff = obj['diff']
            host = diff['host_dst']
            qemu_img = qemu_img_util.QemuImg(dst_cloud.config.dst,
                                             dst_cloud.config.migrate,
                                             host)
            diff_path = diff['path_dst']
            backing_path = qemu_img.detect_backing_file(diff_path, None)
            backing_dir = os.path.dirname(backing_path)
            new_backing_path = os.path.join(backing_dir, new_backing_file)
            qemu_img.diff_rebase(new_backing_path, diff_path)
