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

from cloudferrylib.base import clients
from cloudferrylib.base import resource


class Image(resource.Resource):

    def __init__(self, config):
        self.config = config
        super(Image, self).__init__()

    def get_backend(self):
        return self.config.image.backend


def glance_image_download_cmd(config, image_id, destination_file):
    """Generates glance command which stores `image_id` in `destination_file`

    :returns: Openstack CLI command
    """
    image_download_cmd = clients.os_cli_cmd(
        config, 'glance', 'image-download', image_id)

    return "{img_download_cmd} > {file}".format(
        img_download_cmd=image_download_cmd,
        file=destination_file)


def glance_image_create_cmd(config, image_name, disk_format, file_path,
                            container_format="bare"):
    """Generates glance command which creates image based on arguments
    provided. Command output is filtered for 'id'

    :returns: Openstack CLI command"""
    if file_path.startswith("http"):
        file_prefix = "location"
    else:
        file_prefix = "file"
    args = ("image-create "
            "--name {image_name} "
            "--disk-format={disk_format} "
            "--container-format={container_format} "
            "--{file_prefix} {file_path}").format(
        image_name=image_name,
        disk_format=disk_format,
        container_format=container_format,
        file_prefix=file_prefix,
        file_path=file_path
    )
    return "{image_create} | grep '\<id\>'".format(
        image_create=clients.os_cli_cmd(config, 'glance', args))
