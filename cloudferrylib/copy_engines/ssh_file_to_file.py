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

import logging

from fabric import api
from oslo_config import cfg

from cloudferrylib.copy_engines import base
from cloudferrylib.utils import cmd_cfg
from cloudferrylib.utils import utils

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class SSHFileToFile(base.BaseCopier):
    def transfer(self, data):
        if CONF.migrate.direct_compute_transfer:
            return self.transfer_direct(data)

        LOG.debug("| | copy file")
        ssh_ip_src = self.src_cloud.cloud_config.cloud.ssh_host
        ssh_ip_dst = self.dst_cloud.cloud_config.cloud.ssh_host
        with utils.forward_agent(CONF.migrate.key_filename), \
                utils.up_ssh_tunnel(data['host_dst'], ssh_ip_dst,
                                    ssh_ip_src) as port:
            if CONF.migrate.file_compression == "dd":
                dd_dst = cmd_cfg.dd_cmd_of
                ssh_cmd_dst = cmd_cfg.ssh_cmd_port
                ssh_dst = ssh_cmd_dst(port, 'localhost', dd_dst)

                dd_src = cmd_cfg.dd_cmd_if
                ssh_cmd_src = cmd_cfg.ssh_cmd
                ssh_src = ssh_cmd_src(data['host_src'], dd_src)

                process = ssh_src >> ssh_dst
                process = process('1M',
                                  data['path_src'],
                                  '1M',
                                  data['path_dst'])

                self.src_cloud.ssh_util.execute(process)

            elif CONF.migrate.file_compression == "gzip":
                dd = cmd_cfg.dd_cmd_of
                gunzip_dd = cmd_cfg.gunzip_cmd >> dd
                ssh_cmd_dst = cmd_cfg.ssh_cmd_port
                ssh_dst = ssh_cmd_dst(port, 'localhost', gunzip_dd)

                gzip_cmd = cmd_cfg.gzip_cmd
                ssh_cmd_src = cmd_cfg.ssh_cmd
                ssh_src = ssh_cmd_src(data['host_src'], gzip_cmd)

                process = ssh_src >> ssh_dst
                process = process(CONF.migrate.level_compression,
                                  data['path_src'], '1M', data['path_dst'])

                self.src_cloud.ssh_util.execute(process)

    def transfer_direct(self, data):
        ssh_attempts = CONF.migrate.ssh_connection_attempts
        LOG.debug("| | copy file")
        if CONF.src.ssh_user != 'root' or CONF.dst.ssh_user != 'root':
            LOG.critical("This operation needs 'sudo' access rights, that is "
                         "currently not implemented in this driver. "
                         "Please use the default driver from "
                         "cloudferrylib/copy_engines/.")
        with api.settings(host_string=data['host_src'],
                          connection_attempts=ssh_attempts), \
                utils.forward_agent(CONF.migrate.key_filename):
            if CONF.migrate.file_compression == "dd":
                dd_dst = cmd_cfg.dd_cmd_of
                ssh_cmd_dst = cmd_cfg.ssh_cmd
                ssh_dst = ssh_cmd_dst(data['host_dst'], dd_dst)

                dd_src = cmd_cfg.dd_cmd_if

                process = dd_src >> ssh_dst
                process = process('1M',
                                  data['path_src'],
                                  '1M',
                                  data['path_dst'])

                self.src_cloud.ssh_util.execute(process,
                                                host_exec=data['host_src'])

            elif CONF.migrate.file_compression == "gzip":
                dd = cmd_cfg.dd_cmd_of
                gunzip_dd = cmd_cfg.gunzip_cmd >> dd
                ssh_cmd_dst = cmd_cfg.ssh_cmd
                ssh_dst = ssh_cmd_dst(data['host_dst'], gunzip_dd)

                gzip_cmd = cmd_cfg.gzip_cmd

                process = gzip_cmd >> ssh_dst
                process = process(CONF.migrate.level_compression,
                                  data['path_src'], '1M', data['path_dst'])

                self.src_cloud.ssh_util.execute(process,
                                                host_exec=data['host_src'])
