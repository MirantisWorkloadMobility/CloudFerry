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
from fabric.api import hide
from fabric.api import run
from fabric.api import settings

from cloudferrylib.utils import driver_transporter
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


# Command templates
dd_src_command = 'dd if=%s of=%slv_part_%s skip=%s bs=1M count=%s'
dd_dst_command = 'dd if=%slv_part_%s of=%s seek=%s bs=1M count=%s'
md5_command = "md5sum %slv_part_%s"
gzip_command = "gzip -f %slv_part_%s"
unzip_command = "gzip -f -d %slv_part_%s.gz"
scp_command = 'scp -o StrictHostKeyChecking=no %slv_part_%s.gz %s@%s:%s'
rm_command = 'rm -rf %slv_part_%s*'
ssh_command = "ssh -o StrictHostKeyChecking=no %s@%s '%s'"


class SSHChunksTransfer(driver_transporter.DriverTransporter):
    def transfer(self, data):
        host_src = data['host_src']
        host_dst = data['host_dst']
        path_src = data['path_src']
        path_dst = data['path_dst']

        ssh_user_src = self.cfg.src.ssh_user
        ssh_sudo_pass_src = self.cfg.src.ssh_sudo_password

        ssh_user_dst = self.cfg.dst.ssh_user
        ssh_sudo_pass_dst = self.cfg.dst.ssh_sudo_password

        src_temp_dir = self.cfg.src.temp
        dst_temp_dir = self.cfg.dst.temp

        attempts_count = self.cfg.migrate.retry
        part_size = self.cfg.migrate.ssh_chunk_size

        part_count, part_modulo = self._calculate_parts_count(data)

        with settings(host_string=host_src,
                      user=ssh_user_src,
                      password=ssh_sudo_pass_src), utils.forward_agent(
                env.key_filename):
            for part in range(part_count):
                success = 0  # marker of successful transport operation
                attempt = 0  # number of retry

                # Create chunk
                if part == range(part_count)[0]:
                    # First chunk
                    command = dd_src_command % (path_src,
                                                src_temp_dir,
                                                part,
                                                0,
                                                part_size)
                elif part == range(part_count)[-1] and part_modulo:
                    # Last chunk
                    command = dd_src_command % (path_src,
                                                src_temp_dir,
                                                part,
                                                part * part_size,
                                                part_modulo)
                else:
                    # All middle chunks
                    command = dd_src_command % (path_src,
                                                src_temp_dir,
                                                part,
                                                part * part_size,
                                                part_size)

                run(command)

                # Calculate source chunk check md5 checksum
                md5_src_out = run(md5_command % (src_temp_dir, part))
                md5_src = md5_src_out.split()[-2]

                # Compress chunk
                run(gzip_command % (src_temp_dir, part))

                while success == 0:
                    # Transport chunk to destination
                    run(scp_command % (src_temp_dir,
                                       part,
                                       ssh_user_dst,
                                       host_dst,
                                       dst_temp_dir))

                    # Unzip chunk (TODO: check exit code; if != 0: retry)
                    run(ssh_command %
                        (ssh_user_dst, host_dst, unzip_command % (dst_temp_dir,
                                                                  part)))

                    # Calculate md5sum on destination
                    md5_dst_out = run(ssh_command %
                                      (ssh_user_dst, host_dst,
                                       md5_command % (dst_temp_dir, part)))
                    md5_dst = md5_dst_out.split()[-2]

                    # Compare source and destination md5 sums;
                    # If not equal - retry with 'attempts_count' times
                    if md5_src == md5_dst:
                        success = 1

                    if not success:
                        attempt += 1
                        LOG.critical("Unable to transfer part %s of %s. "
                                     "Retrying... Attempt %s from %s.",
                                     part, path_src, attempt, attempts_count)
                        if attempt == attempts_count:
                            LOG.error("SSH chunks transfer of %s failed.",
                                      path_src)
                            break
                            # TODO: save state:
                            # chunks count, volume info, and all metadata info
                            # with timestamp and reason, errors info, error
                            # codes
                        continue

                    #  Write chunk on destination
                    if part == range(part_count)[0]:
                        command = dd_dst_command % (dst_temp_dir,
                                                    part,
                                                    path_dst,
                                                    0,
                                                    part_size)
                    elif part == range(part_count)[-1] and part_modulo:
                        command = dd_dst_command % (dst_temp_dir,
                                                    part,
                                                    path_dst,
                                                    part * part_size,
                                                    part_modulo)
                    else:
                        command = dd_dst_command % (dst_temp_dir,
                                                    part,
                                                    path_dst,
                                                    part * part_size,
                                                    part_size)
                    with hide('running'):
                        # Because of password
                        run(ssh_command %
                            (ssh_user_dst, host_dst,
                             'echo %s | sudo -S %s' % (ssh_sudo_pass_dst,
                                                       command)))

                        LOG.info(
                            'Running: %s', ssh_command %
                            (ssh_user_dst, host_dst,
                             'echo %s | sudo -S %s' % ('<password>', command)))

                    # Delete used chunk from both servers
                    run(rm_command % (src_temp_dir, part))
                    run(ssh_command % (ssh_user_dst, host_dst, rm_command %
                                       (dst_temp_dir, part)))

    def _calculate_parts_count(self, data):
        part_size = self.cfg.migrate.ssh_chunk_size

        byte_size = data.get(
            'byte_size',
            utils.get_remote_file_size(data['host_src'],
                                       data['path_src'],
                                       self.cfg.src.ssh_user,
                                       self.cfg.src.ssh_sudo_password))

        mbyte_size = float(byte_size) / (1024 * 1024)
        part_int = int(mbyte_size / part_size)
        part_modulo = mbyte_size % part_size
        part_modulo = (int(part_modulo)
                       if mbyte_size > part_size
                       else part_modulo)

        # Calculate count of chunks
        if not part_modulo:
            part_count = part_int
        else:
            part_count = (part_int + 1)

        return part_count, part_modulo
