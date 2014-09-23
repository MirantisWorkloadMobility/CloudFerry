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


from cloudferrylib.base import storage
from cinderclient.v1 import client as cinder_client


class CinderStorage(storage.Storage):

    """
    The main class for working with Openstack cinder client
    """

    def __init__(self, config):
        self.config = config
        self.cinder_client = self.get_cinder_client(self.config)
        super(CinderStorage, self).__init__()

    def get_cinder_client(self, params):

        """ Getting cinder client """

        return cinder_client.Client(params["user"],
                                    params["password"],
                                    params["tenant"],
                                    "http://%s:35357/v2.0/" % params["host"])

    def get_volumes_list(self, detailed=True, search_opts=None):
        return self.cinder_client.volumes.list(detailed, search_opts)

    def create_volume(self, size, **kwargs):
        return self.cinder_client.volumes.create(size, **kwargs)

    def delete_volume(self, volume_id):
        volume = self.__get_volume_by_id(volume_id)
        self.cinder_client.volumes.delete(volume)

    def __get_volume_by_id(self, volume_id):
        return self.cinder_client.volumes.get(volume_id)
    
    def update_volume(self, volume_id, **kwargs):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.update(volume, **kwargs)

    def attach_volume(self, volume_id, instance_id, mountpoint, mode='rw'):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.attach(volume,
                                                 instance_uuid=instance_id,
                                                 mountpoint=mountpoint,
                                                 mode=mode)

    def detach_volume(self, volume_id):
        return self.cinder_client.volumes.detach(volume_id)

    def upload_volume_to_image(self, volume_id, force, image_name,
                               container_format, disk_format):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.upload_to_image(
            volume=volume,
            force=force,
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format)
