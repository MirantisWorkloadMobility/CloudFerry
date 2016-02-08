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

from fabric.api import run, settings, env
import copy

from cloudferrylib.utils import log
from cloudferrylib.utils import utils

LOG = log.getLogger(__name__)


def transfer_file_to_file(src_cloud,
                          dst_cloud,
                          host_src,
                          host_dst,
                          path_src,
                          path_dst,
                          cfg_migrate):
    # TODO: Delete after transport_db_via_ssh action rewriting
    LOG.debug("| | copy file")
    ssh_ip_src = src_cloud.cloud_config.cloud.ssh_host
    ssh_ip_dst = dst_cloud.cloud_config.cloud.ssh_host
    with settings(host_string=ssh_ip_src,
                  connection_attempts=env.connection_attempts):
        with utils.forward_agent(cfg_migrate.key_filename):
            with utils.up_ssh_tunnel(host_dst, ssh_ip_dst, ssh_ip_src) as port:
                if cfg_migrate.file_compression == "dd":
                    run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M " +
                         "if=%s' | ssh -oStrictHostKeyChecking=no " +
                         "-p %s localhost 'dd bs=1M of=%s'") %
                        (host_src, path_src, port, path_dst))
                elif cfg_migrate.file_compression == "gzip":
                    run(("ssh -oStrictHostKeyChecking=no " +
                         "%s 'gzip -%s -c %s' " +
                         "| ssh -oStrictHostKeyChecking=no -p %s localhost " +
                         "'gunzip | dd bs=1M of=%s'") %
                        (host_src, cfg_migrate.level_compression,
                         path_src, port, path_dst))


def delete_file_from_rbd(ssh_ip, file_path):
    with settings(host_string=ssh_ip,
                  connection_attempts=env.connection_attempts):
        with utils.forward_agent(env.key_filename):
            run("rbd rm %s" % file_path)


def convert_to_dest(data, source, dest):
    d = copy.copy(data)
    d[dest] = d['meta'][dest]
    d['meta'][source] = d[source]
    return d


def require_methods(methods, obj):
    for method in dir(obj):
        if method not in methods:
            return False
    return True


def select_boot_volume(info):
    for k, v in info[utils.STORAGE_RESOURCE][utils.VOLUMES_TYPE].iteritems():
        if not((v['num_device'] == 0) and v['bootable']):
            del info[utils.STORAGE_RESOURCE][utils.VOLUMES_TYPE][k]
    return info
