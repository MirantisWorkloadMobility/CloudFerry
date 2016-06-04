# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
import logging
import random

from cloudferry.lib.utils import files
from cloudferry.lib.utils import remote_runner
from cloudferry.lib.copy_engines import base

LOG = logging.getLogger(__name__)


class CopyFailed(RuntimeError):
    pass


class CopyMechanism(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def copy(self, context, source_object, destination_object):
        raise NotImplementedError()


class CopyObject(object):
    def __init__(self, host=None, path=None):
        self.host = host
        self.path = path

    def __repr__(self):
        return "{host}:{path}".format(host=self.host, path=self.path)


class RemoteFileCopy(CopyMechanism):
    """Uses one of `rsync`, `bbcp` or `scp` to copy volume files across remote
    nodes. Primarily used for NFS backend."""

    def copy(self, context, source_object, destination_object):
        data = {
            'host_src': source_object.host,
            'path_src': source_object.path,
            'host_dst': destination_object.host,
            'path_dst': destination_object.path
        }

        try:
            copier = base.get_copier_checked(context.src_cloud,
                                             context.dst_cloud,
                                             data)

            copier.transfer(data)
        except (base.FileCopyError,
                base.CopierCannotBeUsed,
                base.CopierNotFound) as e:
            msg = ("Copying file from {src_host}@{src_file} to "
                   "{dst_host}@{dst_file}, error: {err}").format(
                src_host=source_object.host,
                src_file=source_object.path,
                dst_host=destination_object.host,
                dst_file=destination_object.path,
                err=e.message)
            raise CopyFailed(msg)


class CopyRegularFileToBlockDevice(CopyMechanism):
    """Redirects regular file to stdout and copies over ssh tunnel to calling
    node into block device"""

    @staticmethod
    def _generate_session_name():
        return 'copy_{}'.format(random.getrandbits(64))

    def copy(self, context, source_object, destination_object):
        cfg_src = context.cfg.src
        cfg_dst = context.cfg.dst

        src_user = cfg_src.ssh_user
        dst_user = cfg_dst.ssh_user

        src_host = source_object.host
        dst_host = destination_object.host

        rr_src = remote_runner.RemoteRunner(src_host, src_user, sudo=True,
                                            password=cfg_src.ssh_sudo_password)
        rr_dst = remote_runner.RemoteRunner(dst_host, dst_user, sudo=True,
                                            password=cfg_dst.ssh_sudo_password)

        ssh_opts = ('-o UserKnownHostsFile=/dev/null '
                    '-o StrictHostKeyChecking=no')

        # Choose auxiliary port for SSH tunnel
        aux_port_start, aux_port_end = \
            context.cfg.migrate.ssh_transfer_port.split('-')
        aux_port = random.randint(int(aux_port_start), int(aux_port_end))

        session_name = self._generate_session_name()
        try:
            progress_view = ""
            if files.is_installed(rr_src, "pv"):
                src_file_size = files.remote_file_size(rr_src,
                                                       source_object.path)
                progress_view = "pv --size {size} --progress | ".format(
                    size=src_file_size)

            # First step: prepare netcat listening on aux_port on dst and
            # forwarding all the data to block device
            rr_dst.run('screen -S {session_name} -d -m /bin/bash -c '
                       '\'nc -l {aux_port} | dd of={dst_device}\'; sleep 1',
                       session_name=session_name, aux_port=aux_port,
                       dst_device=destination_object.path)

            # Second step: create SSH tunnel between source and destination
            rr_src.run('screen -S {session_name} -d -m ssh {ssh_opts} -L'
                       ' {aux_port}:127.0.0.1:{aux_port} '
                       '{dst_user}@{dst_host}; sleep 1',
                       session_name=session_name, ssh_opts=ssh_opts,
                       aux_port=aux_port, dst_user=dst_user,
                       dst_host=dst_host)

            # Third step: push data through the tunnel
            rr_src.run('/bin/bash -c \'dd if={src_file} | {progress_view} '
                       'nc 127.0.0.1 {aux_port}\'',
                       aux_port=aux_port, progress_view=progress_view,
                       src_file=source_object.path)

        except remote_runner.RemoteExecutionError as e:
            msg = "Cannot copy {src_object} to {dst_object}: {error}"
            msg = msg.format(src_object=source_object,
                             dst_object=destination_object,
                             error=e.message)
            raise CopyFailed(msg)
        finally:
            try:
                rr_src.run('screen -X -S {session_name} quit || true',
                           session_name=session_name)
                rr_dst.run('screen -X -S {session_name} quit || true',
                           session_name=session_name)
            except remote_runner.RemoteExecutionError:
                LOG.error('Failed to close copy sessions', exc_info=True)
