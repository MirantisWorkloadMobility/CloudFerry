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


from fabric.api import env
from fabric.api import run
from fabric.api import settings

from cloudferrylib.os.actions import utils as action_utils
from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import utils

LOG = utils.get_log(__name__)


class SSHFileToCeph(driver_transporter.DriverTransporter):
    def transfer(self, data):
        ssh_ip_src = self.src_cloud.getIpSsh()
        ssh_ip_dst = self.dst_cloud.getIpSsh()
        action_utils.delete_file_from_rbd(ssh_ip_dst, data['name_file_dst'])
        with settings(host_string=ssh_ip_src):
            with utils.forward_agent(env.key_filename):
                run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' | ssh"
                     " -oStrictHostKeyChecking=no %s 'rbd import "
                     "--image-format=2 - %s/%s'") %
                    (data['host_src'],
                     data['source_volume_path'],
                     ssh_ip_dst,
                     data['ceph_pool_dst'],
                     data['name_file_dst']))
