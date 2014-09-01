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


class VolumeTransfer(object):
    """ The main class for gathering information for volumes migrationlib"""
    def __init__(self, volume, instance, image_id, glance_client, obj=None):
        self.id = volume.id if not obj else obj['id']
        self.size = volume.size if not obj else obj['size']
        self.name = volume.display_name if not obj else obj['name']
        self.description = volume.display_description if not obj else obj['description']
        self.volume_type = (None if volume.volume_type == u'None' else volume.volume_type) \
            if not obj else obj['volume_type']
        self.availability_zone = volume.availability_zone if not obj else obj['availability_zone']
        self.device = volume.attachments[0]['device'] if not obj else obj['device']
        self.host = getattr(instance, 'OS-EXT-SRV-ATTR:host') if not obj else obj['host']
        self.image_id = image_id if not obj else obj['image_id']        
        self.glance_client = glance_client
        if hasattr(volume, 'bootable'):
            self.bootable = (True if volume.bootable == 'true' else False)
        else:
            self.bootable = False
        self.bootable = self.bootable if not obj else obj['bootable']

class VolumeTransferDirectly(VolumeTransfer):
    def __init__(self, volume, instance, volume_path):
        super(VolumeTransferDirectly, self).__init__(volume, instance)
        self.volume_path = volume_path

    def get_volume_path(self):
        return self.volume_path

class VolumeTransferViaImage(VolumeTransfer):

    def __init__(self, volume, instance, image_id, glance_client):
        super(VolumeTransferViaImage, self).__init__(volume, instance)
        self.glance_client = glance_client
        self.image_id = image_id
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

    def convert_to_dict(self):
        return {
            '_type_class': VolumeTransfer.__name__,
            'id': self.id,
            'size': self.size,
            'name': self.name,
            'description': self.description,
            'volume_type': self.volume_type,
            'availability_zone': self.availability_zone,
            'device': self.device,
            'host': self.host,
            'image_id': self.image_id,
            'bootable': self.bootable
        }