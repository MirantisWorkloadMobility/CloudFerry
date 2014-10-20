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


from cloudferrylib.base.action import transporter
from cloudferrylib.os.actions import get_info_images


class CopyFromGlanceToGlance(transporter.Transporter):
    def __init__(self, src_cloud, dst_cloud):
        self.src_cloud = src_cloud
        self.dst_cloud = dst_cloud
        super(CopyFromGlanceToGlance, self).__init__()

    def run(self, image_info=None, **kwargs):
        dst_image = self.dst_cloud.resources['image']

        if not image_info:
            action_get_im = get_info_images.GetInfoImages(self.src_cloud)
            image_info = action_get_im.run()

        new_info = dst_image.deploy(image_info['image_data'])
        return new_info
