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


from fabric.api import env
from fabric.api import run
from fabric.api import settings

from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import utils


# Command templates
dd_src_command = 'dd if=%s of=lv_part_%s skip=%s bs=1M count=%s'
dd_dst_command = 'dd if=lv_part_%s of=%s seek=%s bs=1M count=%s'
md5_command = "md5sum lv_part_%s"
gzip_command = "gzip -f lv_part_%s"
unzip_command = "gzip -f -d lv_part_%s.gz"
scp_command = 'scp lv_part_%s.gz %s:%s'
rm_command = 'rm -rf lv_part_%s*'
ssh_command = 'ssh %s %s'


class SSHChunksTransfer(driver_transporter.DriverTransporter):
    def transfer(self, data):
        host_src = data['host_src']
        host_dst = data['host_dst']
        path_src = data['path_src']
        path_dst = data['path_dst']
        byte_size = data['byte_size']

        attempts_count = self.cfg.migrate.retry
        part_size = self.cfg.migrate.ssh_chunk_size
        temp_dir = '/root/'  # take from config

        mbyte_size = float(byte_size) / (1024 * 1024)
        part_int = int(mbyte_size / part_size)
        part_modulo = int(mbyte_size % part_size)

        # Calculate count of chunks
        if not part_modulo:
            part_count = part_int
        else:
            part_count = (part_int + 1)

        with settings(host_string=host_src), utils.forward_agent(
                env.key_filename):
            for part in range(part_count):
                success = 0  # marker of successful transport operation
                attempt = 0  # number of retry

                # Create chunk
                if part == range(part_count)[0]:
                    command = dd_src_command % (path_src, part, 0, part_size)
                elif part == range(part_count)[-1] and part_modulo:
                    command = dd_src_command % (path_src,
                                                part,
                                                part * part_size,
                                                part_modulo)
                else:
                    command = dd_src_command % (path_src,
                                                part,
                                                part * part_size,
                                                part_size)

                run(command)

                # Calculate source chunk check md5 checksum
                md5_src_out = run(md5_command % part)
                md5_src = md5_src_out.stdout

                # Compress chunk
                run(gzip_command % part)

                while success == 0:
                    # Transport chunk to destination
                    run(scp_command % (part, host_dst, temp_dir))

                    # Unzip chunk (TODO: check exit code; if != 0: retry)
                    run(ssh_command % (host_dst, unzip_command % part))

                    # Calculate md5sum on destination
                    md5_dst_out = run(ssh_command % (host_dst,
                                                     md5_command % part))
                    md5_dst = md5_dst_out.stdout

                    # Compare source and dest md5 sums;
                    # If not equal - retry with 'attempts_count' times
                    if md5_src == md5_dst:
                        success = 1

                    if not success:
                        attempt += 1
                        if attempt == attempts_count:
                            break
                            # TODO: save state:
                            # chunks count, volume info, and all metadata info
                            # with timestamp and reason, errors info, error
                            # codes
                        continue

                    #  Write chunk on destination
                    if part == range(part_count)[0]:
                        command = dd_dst_command % (part,
                                                    path_dst,
                                                    0,
                                                    part_size)
                    elif part == range(part_count)[-1] and part_modulo:
                        command = dd_dst_command % (part,
                                                    path_dst,
                                                    part * part_size,
                                                    part_modulo)
                    else:
                        command = dd_dst_command % (part,
                                                    path_dst,
                                                    part * part_size,
                                                    part_size)

                    run(ssh_command % (host_dst, command))

                    # Delete used chunk from both servers
                    run(rm_command % part)
                    run(ssh_command % (host_dst, rm_command % part))
