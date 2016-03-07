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

from cloudferrylib.utils import files
from cloudferrylib.utils import remote_runner
from cloudferrylib.copy_engines import base


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
            copier = base.get_copier(context.src_cloud,
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

    def copy(self, context, source_object, destination_object):
        src_user = context.cfg.src.ssh_user
        dst_user = context.cfg.dst.ssh_user

        src_host = source_object.host
        dst_host = destination_object.host

        rr = remote_runner.RemoteRunner(src_host, src_user)

        ssh_opts = ('-o UserKnownHostsFile=/dev/null '
                    '-o StrictHostKeyChecking=no')

        try:
            progress_view = ""
            if files.is_installed(rr, "pv"):
                src_file_size = files.remote_file_size(rr, source_object.path)
                progress_view = "pv --size {size} --progress | ".format(
                    size=src_file_size)

            copy = ("dd if={src_file} | {progress_view} "
                    "ssh {ssh_opts} {dst_user}@{dst_host} "
                    "'dd of={dst_device}'")
            rr.run(copy.format(src_file=source_object.path,
                               dst_user=dst_user,
                               dst_host=dst_host,
                               ssh_opts=ssh_opts,
                               dst_device=destination_object.path,
                               progress_view=progress_view))
        except remote_runner.RemoteExecutionError as e:
            msg = "Cannot copy {src_object} to {dst_object}: {error}"
            msg = msg.format(src_object=source_object,
                             dst_object=destination_object,
                             error=e.message)
            raise CopyFailed(msg)
