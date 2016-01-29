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


import math
import os

from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import files
from cloudferrylib.utils import log
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import ssh_util

LOG = log.getLogger(__name__)


class FileCopyFailure(RuntimeError):
    pass


def remote_md5_sum(runner, path):
    get_md5 = "md5sum {file}".format(file=path)
    md5 = str(runner.run(get_md5))
    return md5.split(' ')[0]


def remote_gzip(runner, path):
    gzip_file = "gzip -f {split}".format(split=path)
    runner.run(gzip_file)
    zipped_file_name = path + ".gz"
    return zipped_file_name


def remote_scp(runner, dst_user, src_path, dst_host, dst_path):
    scp_file_to_dest = "scp {cipher} -o {opts} {file} {user}@{host}:{path}"
    runner.run(scp_file_to_dest.format(
        opts='StrictHostKeyChecking=no',
        file=src_path,
        user=dst_user,
        path=dst_path,
        host=dst_host,
        cipher=ssh_util.get_cipher_option()))


def verified_file_copy(src_runner, dst_runner, dst_user, src_path, dst_path,
                       dst_host, num_retries):
    """
    Copies :src_path to :dst_path

    Retries :num_retries until MD5 matches or copy ends without errors.
    """
    copy_failed = True
    attempt = 0
    while copy_failed and attempt < num_retries + 1:
        attempt += 1
        try:
            LOG.info("Copying file '%s' to '%s', attempt '%d'",
                     src_path, dst_host, attempt)
            src_md5 = remote_md5_sum(src_runner, src_path)
            remote_scp(src_runner, dst_user, src_path, dst_host, dst_path)
            dst_md5 = remote_md5_sum(dst_runner, dst_path)

            if src_md5 == dst_md5:
                LOG.debug("File '%s' copy succeeded", src_path)
                copy_failed = False
        except remote_runner.RemoteExecutionError as e:
            LOG.warning("Remote command execution failed: %s. Retrying", e)
            rm_file = "rm -f {file}".format(file=dst_path)
            dst_runner.run_ignoring_errors(rm_file)

    if copy_failed:
        raise FileCopyFailure("Unable to copy file '%s' to '%s' host",
                              src_path, dst_host)


def remote_split_file(runner, input, output, start, block_size):
    split_file = ('dd if={input} of={output} skip={start} bs={block_size}M '
                  'count=1').format(input=input,
                                    output=output,
                                    block_size=block_size,
                                    start=start)
    runner.run(split_file)


def remote_unzip(runner, path):
    unzip = "gzip -f -d {file}".format(file=path)
    runner.run(unzip)


def remote_join_file(runner, dest_file, part, start, block_size):
    join = ("dd if={part} of={dest} seek={start} bs={block_size}M "
            "count=1").format(part=part,
                              dest=dest_file,
                              start=start,
                              block_size=block_size)
    runner.run(join)


def remote_rm_file(runner, path):
    rm = "rm -f {file}".format(file=path)
    runner.run(rm)


def file_transfer_engine(config, host, user, password):
    """Factory which either returns RSYNC copier if `rsync` is available on
    destination compute, or `scp` otherwise"""
    copier = RsyncCopier
    if config.migrate.ephemeral_copy_backend == 'rsync':
        try:
            src_runner = remote_runner.RemoteRunner(host,
                                                    user,
                                                    password=password,
                                                    sudo=True)
            LOG.debug("Checking if rsync is installed")
            src_runner.run("rsync --help &>/dev/null")
            LOG.debug("Using rsync copy")
        except remote_runner.RemoteExecutionError:
            LOG.debug("rsync is not available, using scp copy")
            copier = ScpCopier
    elif config.migrate.ephemeral_copy_backend == 'scp':
        copier = ScpCopier
    return copier


class CopyFilesBetweenComputeHosts(driver_transporter.DriverTransporter):
    def transfer(self, data):
        src_host = data['host_src']
        src_user = self.cfg.src.ssh_user
        src_password = self.cfg.src.ssh_sudo_password

        copier = file_transfer_engine(self.cfg, src_host, src_user,
                                      src_password)
        copier(self.src_cloud, self.dst_cloud, self.cfg).transfer(data)


class ScpCopier(driver_transporter.DriverTransporter):
    """Copies file splitting it into gzipped chunks.

    If one chunk failed to copy, retries until succeeds or retry limit reached
    """
    def transfer(self, data):
        src_host = data['host_src']
        src_path = data['path_src']
        dst_host = data['host_dst']
        dst_path = data['path_dst']

        src_user = self.cfg.src.ssh_user
        dst_user = self.cfg.dst.ssh_user
        block_size = self.cfg.migrate.ssh_chunk_size
        num_retries = self.cfg.migrate.retry
        src_password = self.cfg.src.ssh_sudo_password
        dst_password = self.cfg.dst.ssh_sudo_password

        src_runner = remote_runner.RemoteRunner(src_host,
                                                src_user,
                                                password=src_password,
                                                sudo=True)
        dst_runner = remote_runner.RemoteRunner(dst_host,
                                                dst_user,
                                                password=dst_password,
                                                sudo=True)

        file_size = files.remote_file_size_mb(src_runner, src_path)

        partial_files = []

        src_md5 = remote_md5_sum(src_runner, src_path)

        num_blocks = int(math.ceil(float(file_size) / block_size))

        src_temp_dir = os.path.join(os.path.basename(src_path), '.cf.copy')
        dst_temp_dir = os.path.join(os.path.basename(dst_path), '.cf.copy')

        with files.RemoteDir(src_runner, src_temp_dir) as src_temp, \
                files.RemoteDir(dst_runner, dst_temp_dir) as dst_temp:
            for i in xrange(num_blocks):
                part = os.path.basename(src_path) + '.part{i}'.format(i=i)
                part_path = os.path.join(src_temp.dirname, part)
                remote_split_file(src_runner, src_path, part_path, i,
                                  block_size)
                gzipped_path = remote_gzip(src_runner, part_path)
                gzipped_filename = os.path.basename(gzipped_path)
                dst_gzipped_path = os.path.join(dst_temp.dirname,
                                                gzipped_filename)

                verified_file_copy(src_runner, dst_runner, dst_user,
                                   gzipped_path, dst_gzipped_path, dst_host,
                                   num_retries)

                remote_unzip(dst_runner, dst_gzipped_path)
                partial_files.append(os.path.join(dst_temp.dirname, part))

            for i in xrange(num_blocks):
                remote_join_file(dst_runner, dst_path, partial_files[i], i,
                                 block_size)

        dst_md5 = remote_md5_sum(dst_runner, dst_path)

        if src_md5 != dst_md5:
            message = ("Error copying file from '{src_host}:{src_file}' "
                       "to '{dst_host}:{dst_file}'").format(
                src_file=src_path, src_host=src_host, dst_file=dst_path,
                dst_host=dst_host)
            LOG.error(message)
            remote_rm_file(dst_runner, dst_path)
            raise FileCopyFailure(message)


class RsyncCopier(driver_transporter.DriverTransporter):
    """Uses `rsync` to copy files. Used by ephemeral drive copy process"""

    def transfer(self, data):
        src_host = data['host_src']
        src_path = data['path_src']
        dst_host = data['host_dst']
        dst_path = data['path_dst']

        src_user = self.cfg.src.ssh_user
        dst_user = self.cfg.dst.ssh_user
        src_password = self.cfg.src.ssh_sudo_password

        src_runner = remote_runner.RemoteRunner(src_host,
                                                src_user,
                                                password=src_password,
                                                sudo=True)

        ssh_cipher = ssh_util.get_cipher_option()
        ssh_opts = ["UserKnownHostsFile=/dev/null", "StrictHostKeyChecking=no"]

        rsync = ("rsync "
                 "--partial "
                 "--inplace "
                 "--perms "
                 "--times "
                 "--compress "
                 "--verbose "
                 "--progress "
                 "--rsh='ssh {ssh_opts} {ssh_cipher}' "
                 "{source_file} "
                 "{dst_user}@{dst_host}:{dst_path}").format(
            ssh_cipher=ssh_cipher,
            ssh_opts=" ".join(["-o {}".format(opt) for opt in ssh_opts]),
            source_file=src_path,
            dst_user=dst_user,
            dst_host=dst_host,
            dst_path=dst_path)

        src_runner.run_repeat_on_errors(rsync)
