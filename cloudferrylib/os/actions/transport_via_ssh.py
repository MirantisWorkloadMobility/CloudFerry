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

from cloudferrylib.base.action import transporter
from cloudferrylib.base.action import action
from cloudferrylib.os.actions import utils
__author__ = 'mirrorcoder'

FILE_TO_FILE = 1
FILE_TO_CEPH = 2
CEPH_TO_FILE = 3
CEPH_TO_CEPH = 4

CEPH = 'ceph'
ISCSI = 'iscsi'


class DetectAlgorithmStorageTransfer(action.Action):
    def run(self, cloud_src=None, cloud_dst=None, **kwargs):
        backend_storage_src = cloud_src.resources['storage'].get_backend()
        backend_storage_dst = cloud_dst.resources['storage'].get_backend()
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


class TransportFileToFileViaSsh(transporter.Transporter):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, data_for_trans=[], **kwargs):
        for i in data_for_trans:
            host_src = i['host_src']
            host_dst = i['host_dst']
            path_src = i['path_src']
            path_dst = i['path_dst']
            utils.transfer_file_to_file(cloud_src, cloud_dst, host_src, host_dst, path_src, path_dst, cfg.migrate)
        return {}


class TransportCephToFileViaSsh(transporter.Transporter):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, data_for_trans=[], **kwargs):
        for i in data_for_trans:
            host_dst = i['host_dst']
            path_src = i['path_src']
            path_dst = i['path_dst']
            utils.transfer_from_ceph_to_iscsi(cloud_src,
                                              cloud_dst,
                                              host_dst,
                                              path_dst,
                                              path_src.split("/")[0],
                                              path_src.split("/")[1])
        return {}


class TransportFileToCephViaSsh(transporter.Transporter):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, data_for_trans=[], **kwargs):
        for i in data_for_trans:
            path_src = i['path_src']
            path_dst = i['path_dst']
            utils.transfer_from_iscsi_to_ceph(cloud_src,
                                              cloud_dst,
                                              path_src,
                                              path_dst.split("/")[0],
                                              path_dst.split("/")[1])
        return {}


class TransportCephToCephViaSsh(transporter.Transporter):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, data_for_trans=[], **kwargs):
        for i in data_for_trans:
            path_src = i['path_src']
            path_dst = i['path_dst']
            utils.transfer_from_ceph_to_ceph(cloud_src,
                                             cloud_dst,
                                             path_src.split("/")[0],
                                             path_src.split("/")[1],
                                             path_dst.split("/")[0],
                                             path_dst.split("/")[1])
        return {}


class CreateNewVolumes(action.Action):

    def __init__(self, cloud):
        self.cloud = cloud
        super(CreateNewVolumes, self).__init__()

    def run(self, volumes=None, **kwargs):
        storage = self.cloud.resources['storage']
        volumes_new = storage.deploy(volumes)
        return {
            'volumes_new': volumes_new
        }


class GetInfoVolumes(action.Action):

    def __init__(self, cloud, criteria_search_volumes=dict()):
        self.cloud = cloud
        self.criteria_search_volumes = criteria_search_volumes
        super(GetInfoVolumes, self).__init__()

    def run(self, criteria_search_volumes=None, **kwargs):
        storage = self.cloud.resources['storage']
        volumes = storage.read_info(criteria_search_volumes)
        return {
            'storage_data': volumes
        }
