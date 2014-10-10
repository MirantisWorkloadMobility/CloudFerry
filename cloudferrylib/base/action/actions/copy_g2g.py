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

from cloudferrylib.base.action import Transporter


class CopyFromGlanceToGlance(Transporter.Transporter):
    def __init__(self):
        super(CopyFromGlanceToGlance, self).__init__()

    def run(self, src_cloud, dst_cloud):
        src_image = src_cloud.resources['image']
        dst_image = dst_cloud.resources['image']

        image_info = src_image.read_info()
        dst_image.deploy(image_info)
