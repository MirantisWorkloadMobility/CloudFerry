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

from cloudferrylib.utils import utils
from fabric.api import run, settings, env
import copy
from cloudferrylib.utils import utils as utl

LOG = utils.get_log(__name__)

__author__ = 'mirrorcoder'


def transfer_file_to_file(src_cloud, dst_cloud, host_src, host_dst, path_src, path_dst, cfg_migrate):
    LOG.debug("| | copy file")
    ssh_ip_src = src_cloud.getIpSsh()
    ssh_ip_dst = dst_cloud.getIpSsh()
    with settings(host_string=ssh_ip_src):
        with utils.forward_agent(cfg_migrate.key_filename):
            with utils.up_ssh_tunnel(host_dst, ssh_ip_dst) as port:
                if cfg_migrate.file_compression == "dd":
                    run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' " +
                         "| ssh -oStrictHostKeyChecking=no -p %s localhost 'dd bs=1M of=%s'") %
                        (host_src, path_src, port, path_dst))
                elif cfg_migrate.file_compression == "gzip":
                    run(("ssh -oStrictHostKeyChecking=no %s 'gzip -%s -c %s' " +
                         "| ssh -oStrictHostKeyChecking=no -p %s localhost 'gunzip | dd bs=1M of=%s'") %
                        (host_src, cfg_migrate.level_compression,
                         path_src, port, path_dst))


def transfer_from_ceph_to_iscsi(src_cloud,
                                dst_cloud,
                                dst_host,
                                dst_path,
                                ceph_pool_src="volumes",
                                name_file_src="volume-"):
    ssh_ip_src = src_cloud.getIpSsh()
    ssh_ip_dst = dst_cloud.getIpSsh()
    with settings(host_string=ssh_ip_src):
        with utils.forward_agent(env.key_filename):
            with utils.up_ssh_tunnel(dst_host, ssh_ip_dst) as port:
                run(("rbd export -p %s %s - | ssh -oStrictHostKeyChecking=no -p %s localhost " +
                     "'dd bs=1M of=%s'") % (ceph_pool_src, name_file_src, port, dst_path))


def transfer_from_iscsi_to_ceph(src_cloud,
                                dst_cloud,
                                host_src,
                                source_volume_path,
                                ceph_pool_dst="volumes",
                                name_file_dst="volume-"):
    ssh_ip_src = src_cloud.getIpSsh()
    ssh_ip_dst = dst_cloud.getIpSsh()
    delete_file_from_rbd(ssh_ip_dst, ceph_pool_dst, name_file_dst)
    with settings(host_string=ssh_ip_src):
        with utils.forward_agent(env.key_filename):
            run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' | " +
                "ssh -oStrictHostKeyChecking=no %s 'rbd import --image-format=2 - %s/%s'") %
                (host_src, source_volume_path, ssh_ip_dst, ceph_pool_dst, name_file_dst))


def transfer_from_ceph_to_ceph(src_cloud,
                               dst_cloud,
                               host_src=None,
                               host_dst=None,
                               src_path="volumes",
                               dst_path="volumes"):
    if not host_src:
        host_src = src_cloud.getIpSsh()
    if not host_dst:
        host_dst = dst_cloud.getIpSsh()
    delete_file_from_rbd(host_dst, dst_path)
    with settings(host_string=host_src):
        with utils.forward_agent(env.key_filename):
            run(("rbd export %s - | " +
                 "ssh -oStrictHostKeyChecking=no %s 'rbd import --image-format=2 - %s'") %
                (src_path, host_dst, dst_path))


def delete_file_from_rbd(ssh_ip, file_path):
    with settings(host_string=ssh_ip):
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
    for k, v in info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE].iteritems():
        if not((v['num_device'] == 0) and v['bootable']):
            del info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][k]
    return info
