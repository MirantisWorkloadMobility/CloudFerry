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


__author__ = 'mirrorcoder'


class VolumeTransfer:
    """ The main class for gathering information for volumes migrationlib"""
    def __init__(self, volume, instance, image_id, glance_client):
        self.glance_client = glance_client
        self.id = volume.id
        self.size = volume.size
        self.name = volume.display_name
        self.description = volume.display_description
        self.volume_type = None if volume.volume_type == u'None' else volume.volume_type
        self.availability_zone = volume.availability_zone
        self.device = volume.attachments[0]['device']
        self.host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        self.image_id = image_id
        self.bootable = True if volume.bootable == 'true' else False
        self.__info = self.glance_client.images.get(self.image_id)
        self.checksum = self.__info.checksum

    def get_info_image(self):
        return self.__info

    def get_ref_image(self):
        """
        return file-like object which will be using on destination cloud for importing images (aka volumes)
        """
        resp = self.glance_client.images.data(self.image_id)._resp
        return resp

    def delete(self):
        self.glance_client.images.delete(self.image_id)