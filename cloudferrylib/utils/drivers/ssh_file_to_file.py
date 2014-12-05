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


from fabric.api import run
from fabric.api import settings

from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import utils

LOG = utils.get_log(__name__)


class SSHFileToFile(driver_transporter.DriverTransporter):
    def transfer(self, data):
        LOG.debug("| | copy file")
        ssh_ip_src = self.src_cloud.getIpSsh()
        ssh_ip_dst = self.dst_cloud.getIpSsh()
        with settings(host_string=ssh_ip_src):
            with utils.forward_agent(self.cfg.key_filename):
                with utils.up_ssh_tunnel(data['host_dst'], ssh_ip_dst) as port:
                    if self.cfg.file_compression == "dd":
                        run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M "
                             "if=%s' | ssh -oStrictHostKeyChecking=no -p %s "
                             "localhost 'dd bs=1M of=%s'") %
                            (data['host_src'],
                             data['path_src'],
                             port,
                             data['path_dst']))
                    elif self.cfg.file_compression == "gzip":
                        run(("ssh -oStrictHostKeyChecking=no %s 'gzip -%s -c "
                             "%s' | ssh -oStrictHostKeyChecking=no -p %s "
                             "localhost 'gunzip | dd bs=1M of=%s'") %
                            (data['host_src'],
                             self.cfg.level_compression,
                             data['path_src'],
                             port,
                             data['path_dst']))
