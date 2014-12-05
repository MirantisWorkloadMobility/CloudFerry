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


class SSHCephToCeph(driver_transporter.DriverTransporter):
    def transfer(self, data):
        host_src = (data.get('host_src') if data.get('host_src')
                    else self.src_cloud.getIpSsh())
        host_dst = (data.get('host_dst') if data.get('host_dst')
                    else self.dst_cloud.getIpSsh())
        action_utils.delete_file_from_rbd(host_dst, data['dst_path'])
        with settings(host_string=host_src):
            with utils.forward_agent(env.key_filename):
                run(("rbd export %s - | " +
                     "ssh -oStrictHostKeyChecking=no %s 'rbd import "
                     "--image-format=2 - %s'") %
                    (data['src_path'],
                     host_dst,
                     data['dst_path']))
