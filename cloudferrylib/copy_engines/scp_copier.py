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

from cloudferrylib.copy_engines import base
from cloudferrylib.utils import files
from cloudferrylib.utils import retrying
from cloudferrylib.utils import sizeof_format
from cloudferrylib.utils import ssh_util

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class ScpCopier(base.BaseCopier):
    """Copies file splitting it into gzipped chunks.

    If one chunk failed to copy, retries until succeeds or retry limit reached
    """

    name = 'scp'

    def run_scp(self, runner, src_path, dst_host, dst_path):
        """
        Copy a file from source host to destination by scp.

        :param runner: Runner to run a command on source host.
        :param src_path: Path to a file on source host.
        :param dst_host: Destination host.
        :param dst_path: Path to a file on destination host.
        :raise: FileCopyError in case the file was not copied by any reasons.
        """
        data = {'host_src': runner.host,
                'path_src': src_path,
                'host_dst': dst_host,
                'path_dst': dst_path}

        retrier = retrying.Retry(
            max_attempts=CONF.migrate.retry,
            predicate=self.verify,
            predicate_kwargs={'data': data},
            timeout=0,
        )
        LOG.info("Copying file '%s' to '%s'", src_path, dst_host)
        cmd = "scp {cipher} -o {opts} {file} {user}@{host}:{path}"
        try:
            retrier.run(runner.run, cmd, opts='StrictHostKeyChecking=no',
                        file=src_path, user=CONF.dst.ssh_user, host=dst_host,
                        path=dst_path, cipher=ssh_util.get_cipher_option())
        except retrying.MaxAttemptsReached:
            raise base.FileCopyError(**data)

    def transfer(self, data):
        src_host = data['host_src']
        src_path = data['path_src']
        dst_host = data['host_dst']
        dst_path = data['path_dst']

        src_runner = self.runner(src_host, 'src')
        dst_runner = self.runner(dst_host, 'dst')

        block_size = CONF.migrate.ssh_chunk_size
        file_size = files.remote_file_size_mb(src_runner, src_path)
        num_blocks = int(math.ceil(float(file_size) / block_size))

        src_temp_dir = os.path.join(os.path.basename(src_path), '.cf.copy')
        dst_temp_dir = os.path.join(os.path.basename(dst_path), '.cf.copy')

        partial_files = []
        with files.RemoteDir(src_runner, src_temp_dir) as src_temp, \
                files.RemoteDir(dst_runner, dst_temp_dir) as dst_temp:
            for i in xrange(num_blocks):
                part = os.path.basename(src_path) + '.part{i}'.format(i=i)
                part_path = os.path.join(src_temp.dirname, part)
                files.remote_split_file(src_runner, src_path, part_path, i,
                                        block_size)
                gzipped_path = files.remote_gzip(src_runner, part_path)
                gzipped_filename = os.path.basename(gzipped_path)
                dst_gzipped_path = os.path.join(dst_temp.dirname,
                                                gzipped_filename)

                self.run_scp(src_runner, gzipped_path, dst_host,
                             dst_gzipped_path)

                files.remote_unzip(dst_runner, dst_gzipped_path)
                partial_files.append(os.path.join(dst_temp.dirname, part))

            for i in xrange(num_blocks):
                files.remote_join_file(dst_runner, dst_path, partial_files[i],
                                       i, block_size)
        if not self.verify(data):
            self.clean_dst(data)
            raise base.FileCopyError(**data)

    def verify(self, data):
        """
        Verification that the file has been copied correctly.

        :param data: The dictionary with necessary information
        :return: True or False
        """
        src_host = data['host_src']
        src_path = data['path_src']
        dst_host = data['host_dst']
        dst_path = data['path_dst']
        src_runner = self.runner(src_host, 'src')
        dst_runner = self.runner(dst_host, 'dst')

        src_size = files.remote_file_size(src_runner, src_path)
        dst_size = files.remote_file_size(dst_runner, dst_path)
        if src_size != dst_size:
            LOG.warning("The sizes of '%s' (%s) and '%s' (%s) are mismatch",
                        src_path, sizeof_format.sizeof_fmt(src_size),
                        dst_path, sizeof_format.sizeof_fmt(dst_size))
            return False

        if CONF.migrate.copy_with_md5_verification:
            LOG.info("Running md5 checksum calculation on the file '%s' with "
                     "size %s on host '%s'",
                     src_path, sizeof_format.sizeof_fmt(src_size), src_host)
            src_md5 = files.remote_md5_sum(src_runner, src_path)
            LOG.info("Running md5 checksum calculation on the file '%s' with "
                     "size %s on host '%s'",
                     dst_path, sizeof_format.sizeof_fmt(dst_size), dst_host)
            dst_md5 = files.remote_md5_sum(dst_runner, dst_path)
            if src_md5 != dst_md5:
                LOG.warning("The md5 checksums of '%s' (%s) and '%s' (%s) are "
                            "mismatch", src_path, src_md5, dst_path, dst_md5)
                return False

        return True
