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

import os
import subprocess
import uuid

from fabric.api import env

from cloudferrylib.base.action import action
from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import files
from cloudferrylib.utils import log
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import ssh_util
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)


class CheckBandwidth(action.Action):
    """Assesses networking bandwidth between CloudFerry node and controller
    node defined in `[src|dst] host` config variable.

    Process:
     1. Generate file of size `[initial_check] test_file_size` on CF node;
     2. Copy generated file to `[src|dst] host` over network (scp);
     3. Measure time required for file to be copied over;
     4. Calculate networking bandwidth based on measuring above;
     5. If bandwidth is smaller than `[initial_check] claimed_bandwidth` *
        `[initial_check] factor` - stop migration and display error message.

    Config options:
     - `[initial_check] test_file_size` - size of the file to be copied over;
     - `[initial_check] claimed_bandwidth` - expected bandwidth;
     - `[initial_check] factor` - fraction of 1 for the lowest acceptable
        bandwidth, e.g. `factor = 0.5` means expected bandwidth should not get
        below `0.5 * claimed_bandwidth`;
     - `[src|dst] host` - host the file will be copied to.
    """

    def run(self, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        runner = remote_runner.RemoteRunner(cfg.ssh_host, cfg.ssh_user)

        temp_dir_name = os.popen('mktemp -dt check_band_XXXX').read().rstrip()
        temp_file_name = str(uuid.uuid4())

        claimed_bandw = self.cloud.cloud_config.initial_check.claimed_bandwidth
        test_file_size = self.cloud.cloud_config.initial_check.test_file_size

        ssh_user = self.cloud.cloud_config.cloud.ssh_user

        factor = self.cloud.cloud_config.initial_check.factor
        req_bandwidth = claimed_bandw * factor

        local_file_path = os.path.join(temp_dir_name, temp_file_name)
        remote_file_path = os.path.join(temp_dir_name,
                                        temp_file_name)

        scp_upload = cmd_cfg.scp_cmd(ssh_util.get_cipher_option(),
                                     '',
                                     ssh_user,
                                     cfg.ssh_host,
                                     remote_file_path,
                                     temp_dir_name)

        scp_download = cmd_cfg.scp_cmd(ssh_util.get_cipher_option(),
                                       local_file_path,
                                       ssh_user,
                                       cfg.ssh_host,
                                       temp_dir_name,
                                       '')

        with files.RemoteDir(runner, temp_dir_name):
            try:
                with utils.forward_agent(env.key_filename):
                    dd_command = cmd_cfg.dd_full('/dev/zero',
                                                 remote_file_path,
                                                 1,
                                                 0,
                                                 test_file_size)
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
                if len(temp_dir_name) > 1:
                    os.system("rm -rf {}".format(temp_dir_name))
                else:
                    raise RuntimeError('Wrong dirname %s, stopping' %
                                       temp_dir_name)

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
