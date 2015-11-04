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

from cloudferrylib.base import resource


class Storage(resource.Resource):

    def __init__(self, config):
        self.config = config
        super(Storage, self).__init__()

    def get_backend(self):
        return self.config.storage.backend

    def attach_volume_to_instance(self, volume_info):
        raise NotImplementedError("it's base class")

    def get_volumes_list(self, detailed=True, search_opts=None):
        raise NotImplementedError("it's base class")

    def create_volume(self, size, **kwargs):
        raise NotImplementedError("it's base class")

    def delete_volume(self, volume_id):
        raise NotImplementedError("it's base class")

    def get_volume_by_id(self, volume_id):
        raise NotImplementedError("it's base class")

    def update_volume(self, volume_id, **kwargs):
        raise NotImplementedError("it's base class")

    def attach_volume(self, volume_id, instance_id, mountpoint, mode='rw'):
        raise NotImplementedError("it's base class")

    def detach_volume(self, volume_id):
        raise NotImplementedError("it's base class")

    def upload_volume_to_image(self, volume_id, force, image_name,
                               container_format, disk_format):
        raise NotImplementedError("it's base class")
