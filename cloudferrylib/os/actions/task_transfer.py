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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl

from cloudferrylib.utils.drivers import ssh_file_to_file
from cloudferrylib.utils.drivers import ssh_ceph_to_ceph
from cloudferrylib.utils.drivers import ssh_ceph_to_file
from cloudferrylib.utils.drivers import ssh_file_to_ceph


DRIVER_MAP = {'ssh_file_to_file': ssh_file_to_file.SSHFileToFile,
              'ssh_file_to_ceph': ssh_file_to_ceph.SSHFileToCeph,
              'ssh_ceph_to_file': ssh_ceph_to_file.SSHCephToFile,
              'ssh_ceph_to_ceph': ssh_ceph_to_ceph.SSHCephToCeph}


class TaskTransfer(action.Action):
    def __init__(self, init, driver,
                 input_info='info',
                 resource_name=utl.VOLUMES_TYPE,
                 resource_root_name=utl.VOLUME_BODY):
        super(TaskTransfer, self).__init__(init)
        self.driver = DRIVER_MAP[driver](self.src_cloud,
                                         self.dst_cloud,
                                         self.cfg)
        self.resource_name = resource_name
        self.resource_root_name = resource_root_name
        self.input_info = input_info

    def run(self, **kwargs):
        info = kwargs[self.input_info]
        data_for_trans = info[self.resource_name]

        for item in data_for_trans.itervalues():
            data = item[self.resource_root_name]
            self.driver.transfer(data)

        return {}
