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
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils import utils as utl


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


TRANSPORTER_MAP = {CEPH: {CEPH: 'SSHCephToCeph',
                          ISCSI: 'SSHCephToFile'},
                   ISCSI: {CEPH: 'SSHFileToCeph',
                           ISCSI: 'SSHFileToFile'}}


class PostTransportInstance(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        # Init before run
        src_compute = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        dst_compute = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
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
            if ((instance_boot == utl.BOOT_FROM_IMAGE) and
                    (backend_ephem_drv_src == ISCSI) and
                    (backend_ephem_drv_dst == ISCSI)):
                self.copy_diff_file(self.src_cloud,
                                    self.dst_cloud,
                                    one_instance)

            new_info[utl.INSTANCES_TYPE].update(
                one_instance[utl.INSTANCES_TYPE])

        return {
            'info': new_info
        }

    def copy_data_via_ssh(self,
                          src_cloud,
                          dst_cloud,
                          info,
                          body,
                          resources,
                          types):
        dst_storage = dst_cloud.resources[resources]
        src_compute = src_cloud.resources[resources]
        src_backend = src_compute.config.compute.backend
        dst_backend = dst_storage.config.compute.backend
        transporter = task_transfer.TaskTransfer(
            self.init,
            TRANSPORTER_MAP[src_backend][dst_backend],
            resource_name=types,
            resource_root_name=body)
        transporter.run(info=info)

    def copy_diff_file(self, src_cloud, dst_cloud, info):
        self.copy_data_via_ssh(src_cloud,
                               dst_cloud,
                               info,
                               utl.DIFF_BODY,
                               utl.COMPUTE_RESOURCE,
                               utl.INSTANCES_TYPE)
