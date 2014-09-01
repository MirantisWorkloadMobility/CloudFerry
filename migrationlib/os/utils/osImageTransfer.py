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


class ImageTransfer:

    def __init__(self, image_id, glance_client):
        self.glance_client = glance_client
        self.image_id = image_id
        self.__info = self.glance_client.images.get(image_id)
        self.checksum = self.__info.checksum

    def get_info_image(self):
        return self.__info

    def get_ref_image(self):
        return self.glance_client.images.data(self.image_id)._resp

    def delete(self):
        self.glance_client.images.delete(self.image_id)

    def convert_to_dict(self):
        return {
            '_type_class': ImageTransfer.__name__,
            'image_id': self.image_id
        }
