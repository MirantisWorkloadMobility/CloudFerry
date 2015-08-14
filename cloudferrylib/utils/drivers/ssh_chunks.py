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


import os
import math

from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import files
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class FileCopyFailure(RuntimeError):
    pass


def splitter(total_size, block_size):
    """Splits :total_size into :block_size smaller chunks

    :returns generator with (start, end) tuple"""

    start = 0
    end = start
    while start <= total_size:
        end += block_size
        if end > total_size:
            end = total_size
        yield start, end
        start = end + 1


def remote_file_size(runner, path):
    return int(runner.run('stat --printf="%s" {path}'.format(path=path)))


def remote_file_size_mb(runner, path):
    return int(math.ceil(remote_file_size(runner, path) / (1024.0 * 1024.0)))


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
    scp_file_to_dest = "scp -o {opts} {file} {user}@{host}:{path}".format(
        opts='StrictHostKeyChecking=no',
        file=src_path,
        user=dst_user,
        path=dst_path,
        host=dst_host)
    runner.run(scp_file_to_dest)


def verified_file_copy(src_runner, dst_runner, dst_user, src_path, dst_path,
                       dst_host, num_retries):
    """
    Copies :src_path to :dst_path

    Retries :num_retries until MD5 matches or copy ends without errors.
    """
    copy_failed = True
    attempt = 0
    while copy_failed and attempt < num_retries+1:
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


def remote_split_file(runner, input, output, start, end):
    split_file = ('dd if={input} of={output} skip={start} bs={block_size} '
                  'count={blocks_to_copy}').format(input=input, output=output,
                                                   block_size='1M',
                                                   start=start,
                                                   blocks_to_copy=end-start)
    runner.run(split_file)


def remote_unzip(runner, path):
    unzip = "gzip -f -d {file}".format(file=path)
    runner.run(unzip)


def remote_join_file(runner, dest_file, part, start, end):
    join = ("dd if={part} of={dest} seek={start} bs={block_size} "
            "count={blocks_to_copy}").format(part=part, dest=dest_file,
                                             start=start,
                                             block_size='1M',
                                             blocks_to_copy=end-start)
    runner.run(join)


def remote_rm_file(runner, path):
    rm = "rm -f {file}".format(file=path)
    runner.run(rm)


class CopyFilesBetweenComputeHosts(driver_transporter.DriverTransporter):
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

        file_size = remote_file_size_mb(src_runner, src_path)

        with files.RemoteTempDir(src_runner) as src_temp_dir,\
                files.RemoteTempDir(dst_runner) as dst_temp_dir:
            partial_files = []

            src_md5 = remote_md5_sum(src_runner, src_path)

            for i, (start, end) in enumerate(splitter(file_size, block_size)):
                part = os.path.basename(src_path) + '.part{i}'.format(i=i)
                part_path = os.path.join(src_temp_dir, part)
                remote_split_file(src_runner, src_path, part_path,
                                  start, end)
                gzipped_path = remote_gzip(src_runner, part_path)
                gzipped_filename = os.path.basename(gzipped_path)
                dst_path = os.path.join(dst_temp_dir, gzipped_filename)

                verified_file_copy(src_runner, dst_runner, dst_user,
                                   gzipped_path, dst_path, dst_host,
                                   num_retries)

                remote_unzip(dst_runner, dst_path)
                partial_files.append(os.path.join(dst_temp_dir, part))

            for i, (start, end) in enumerate(splitter(file_size, block_size)):
                remote_join_file(dst_runner, dst_path, partial_files[i],
                                 start, end)

            dst_md5 = remote_md5_sum(dst_runner, dst_path)

            if src_md5 != dst_md5:
                message = ("Error copying file from '{src_file}@{src_host}' "
                           "to '{dst_file}@{dst_host}'").format(
                    src_file=src_path, src_host=src_host, dst_file=dst_path,
                    dst_host=dst_host)
                LOG.error(message)
                remote_rm_file(dst_runner, dst_path)
                raise FileCopyFailure(message)
