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


from cloudferry.lib.base.action import action
from cloudferry.lib.utils import utils as utl

FILE_TO_FILE = 1
FILE_TO_CEPH = 2
CEPH_TO_FILE = 3
CEPH_TO_CEPH = 4

CEPH = 'ceph'
ISCSI = 'iscsi'


class DetectAlgorithmStorageTransfer(action.Action):
    def run(self, src_cloud, dst_cloud, **kwargs):
        backend_storage_src = src_cloud.resources[
            utl.STORAGE_RESOURCE].get_backend()
        backend_storage_dst = dst_cloud.resources[
            utl.STORAGE_RESOURCE].get_backend()
        res = 0
        if backend_storage_src == ISCSI:
            if backend_storage_dst == ISCSI:
                res = FILE_TO_FILE
            elif backend_storage_dst == CEPH:
                res = FILE_TO_CEPH
        elif backend_storage_src == CEPH:
            if backend_storage_dst == ISCSI:
                res = CEPH_TO_FILE
            elif backend_storage_dst == CEPH:
                res = CEPH_TO_CEPH
        self.set_next_path(res)
        return {
            '__num_algorithm': res
        }
