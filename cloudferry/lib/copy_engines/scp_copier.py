# Copyright (c) 2016 Mirantis Inc.
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
import math
import os

from oslo_config import cfg

from cloudferry.lib.copy_engines import base
from cloudferry.lib.utils import files
from cloudferry.lib.utils import local
from cloudferry.lib.utils import retrying
from cloudferry.lib.utils import sizeof_format
from cloudferry.lib.utils import ssh_util

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class ScpCopier(base.BaseCopier):
    """Copies file splitting it into gzipped chunks.

    If one chunk failed to copy, retries until succeeds or retry limit reached
    """

    name = 'scp'

    def run_scp(self, host_src, path_src, host_dst, path_dst, gateway=None):
        """
        Copy a file from source host to destination by scp.

        :param host_src: Source host.
        :param path_src: Path to a file on source host.
        :param host_dst: Destination host.
        :param path_dst: Path to a file on destination host.
        :raise: FileCopyError in case the file was not copied by any reasons.
        """
        cmd = "scp {ssh_opts} {src} {dst}"

        if CONF.migrate.direct_transfer:
            src = path_src
            runner = self.runner(host_src, 'src', gateway)
            run = runner.run
        else:
            # -3: Copies between two remote hosts are transferred through
            # the local host.
            src = '-3 {src_user}@{src_host}:{src_path}'.format(
                src_user=CONF.src.ssh_user,
                src_host=host_src,
                src_path=path_src,
            )
            run = local.run
        dst = '{dst_user}@{dst_host}:{dst_path}'.format(
            dst_user=CONF.dst.ssh_user,
            dst_host=host_dst,
            dst_path=path_dst,
        )

        kwargs = {'host_src': host_src,
                  'path_src': path_src,
                  'host_dst': host_dst,
                  'path_dst': path_dst,
                  'gateway': gateway}

        retrier = retrying.Retry(
            max_attempts=CONF.migrate.retry,
            predicate=self.verify,
            predicate_kwargs=kwargs,
        )
        LOG.info("Copying file '%s' to '%s'", path_src, host_dst)
        try:
            retrier.run(run, cmd.format(
                ssh_opts=ssh_util.default_ssh_options(),
                src=src,
                dst=dst),
                        capture_output=False)
        except retrying.MaxAttemptsReached:
            self.clean_dst(host_dst, path_dst)
            raise base.FileCopyError(host_src=host_src,
                                     path_src=path_src,
                                     host_dst=host_dst,
                                     path_dst=path_dst)

    def transfer(self, data):
        host_src = data['host_src']
        path_src = data['path_src']
        host_dst = data['host_dst']
        path_dst = data['path_dst']
        gateway = data.get('gateway')

        src_runner = self.runner(host_src, 'src', gateway)
        dst_runner = self.runner(host_dst, 'dst', gateway)

        block_size = CONF.migrate.ssh_chunk_size
        file_size = files.remote_file_size_mb(src_runner, path_src)
        num_blocks = int(math.ceil(float(file_size) / block_size))

        src_temp_dir = os.path.join(os.path.basename(path_src), '.cf.copy')
        dst_temp_dir = os.path.join(os.path.basename(path_dst), '.cf.copy')

        partial_files = []
        with files.RemoteDir(src_runner, src_temp_dir) as src_temp, \
                files.RemoteDir(dst_runner, dst_temp_dir) as dst_temp:
            for i in xrange(num_blocks):
                part = os.path.basename(path_src) + '.part{i}'.format(i=i)
                part_path = os.path.join(src_temp.dirname, part)
                files.remote_split_file(src_runner, path_src, part_path, i,
                                        block_size)
                gzipped_path = files.remote_gzip(src_runner, part_path)
                gzipped_filename = os.path.basename(gzipped_path)
                dst_gzipped_path = os.path.join(dst_temp.dirname,
                                                gzipped_filename)

                self.run_scp(host_src, gzipped_path, host_dst,
                             dst_gzipped_path, gateway)

                files.remote_unzip(dst_runner, dst_gzipped_path)
                partial_files.append(os.path.join(dst_temp.dirname, part))

            for i in xrange(num_blocks):
                files.remote_join_file(dst_runner, path_dst, partial_files[i],
                                       i, block_size)
        if not self.verify(host_src, path_src, host_dst, path_dst, gateway):
            self.clean_dst(host_dst, path_dst)
            raise base.FileCopyError(**data)

    def verify(self, host_src, path_src, host_dst, path_dst, gateway=None):
        """
        Verification that the file has been copied correctly.

        :param data: The dictionary with necessary information
        :return: True or False
        """
        src_runner = self.runner(host_src, 'src', gateway)
        dst_runner = self.runner(host_dst, 'dst', gateway)

        src_size = files.remote_file_size(src_runner, path_src)
        dst_size = files.remote_file_size(dst_runner, path_dst)
        if src_size != dst_size:
            LOG.warning("The sizes of '%s' (%s) and '%s' (%s) are mismatch",
                        path_src, sizeof_format.sizeof_fmt(src_size),
                        path_dst, sizeof_format.sizeof_fmt(dst_size))
            return False

        if CONF.migrate.copy_with_md5_verification:
            LOG.info("Running md5 checksum calculation on the file '%s' with "
                     "size %s on host '%s'",
                     path_src, sizeof_format.sizeof_fmt(src_size), host_src)
            src_md5 = files.remote_md5_sum(src_runner, path_src)
            LOG.info("Running md5 checksum calculation on the file '%s' with "
                     "size %s on host '%s'",
                     path_dst, sizeof_format.sizeof_fmt(dst_size), host_dst)
            dst_md5 = files.remote_md5_sum(dst_runner, path_dst)
            if src_md5 != dst_md5:
                LOG.warning("The md5 checksums of '%s' (%s) and '%s' (%s) are "
                            "mismatch", path_src, src_md5, path_dst, dst_md5)
                return False

        return True
