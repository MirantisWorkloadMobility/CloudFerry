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


import subprocess
import uuid

from fabric.api import env

from cloudferrylib.base.action import action
from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class CheckBandwidth(action.Action):
    def run(self, **kwargs):
        claimed_bandw = self.cloud.cloud_config.initial_check.claimed_bandwidth
        test_file_size = self.cloud.cloud_config.initial_check.test_file_size

        ssh_user = self.cloud.cloud_config.cloud.ssh_user

        factor = self.cloud.cloud_config.initial_check.factor
        req_bandwidth = claimed_bandw * factor
        temp_file_name = str(uuid.uuid4())
        local_file_path = '/tmp/' + temp_file_name
        remote_file_path = '%s/%s' % (self.cloud.cloud_config.cloud.temp,
                                      temp_file_name)

        scp_upload = cmd_cfg.scp_cmd('',
                                     ssh_user,
                                     self.cloud.cloud_config.cloud.ssh_host,
                                     remote_file_path,
                                     '/tmp/')

        scp_download = cmd_cfg.scp_cmd(local_file_path,
                                       ssh_user,
                                       self.cloud.cloud_config.cloud.ssh_host,
                                       self.cloud.cloud_config.cloud.temp,
                                       '')

        check_dir_cmd = cmd_cfg.mkdir_cmd(self.cloud.cloud_config.cloud.temp)
        self.cloud.ssh_util.execute(check_dir_cmd)

        try:
            with utils.forward_agent(env.key_filename):
                dd_command = cmd_cfg.dd_full('/dev/zero', remote_file_path, 1,
                                             0, test_file_size)
                self.cloud.ssh_util.execute(dd_command)

                LOG.info("Checking upload speed... Wait please.")
                period_upload = utils.timer(subprocess.call,
                                            str(scp_upload),
                                            shell=True)

                LOG.info("Checking download speed... Wait please.")
                period_download = utils.timer(subprocess.call,
                                              str(scp_download),
                                              shell=True)
        finally:
            self.cloud.ssh_util.execute(cmd_cfg.rm_cmd(remote_file_path))
            subprocess.call(str(cmd_cfg.rm_cmd(local_file_path)), shell=True)

        # To have Megabits per second
        upload_speed = test_file_size / period_upload * 8
        download_speed = test_file_size / period_download * 8

        if upload_speed < req_bandwidth or download_speed < req_bandwidth:
            raise RuntimeError('Bandwidth is not OK. '
                               'Claimed bandwidth: %s Mb/s. '
                               'Required speed: %s Mb/s. '
                               'Actual upload speed: %.2f Mb/s. '
                               'Actual download speed: %.2f Mb/s. '
                               'Aborting migration...' %
                               (claimed_bandw,
                                req_bandwidth,
                                upload_speed,
                                download_speed))

        LOG.info("Bandwith is OK. "
                 "Required speed: %.2f Mb/s. "
                 "Upload speed: %.2f Mb/s. "
                 "Download speed: %.2f Mb/s",
                 req_bandwidth,
                 upload_speed,
                 download_speed)
