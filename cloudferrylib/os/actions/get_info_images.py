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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class GetInfoImages(action.Action):

    def __init__(self, init, cloud=None, search_opts=dict()):
        super(GetInfoImages, self).__init__(init, cloud)
        self.search_opts = search_opts

    def run(self, **kwargs):
        """Get info about images or specified image.

        :param image_id: Id of specified image
        :param image_name: Name of specified image
        :param images_list: List of names/id's of images
        :rtype: Dictionary with image data
        """
        search_opts = kwargs.get('search_opts_img', self.search_opts)
        search_opts.update(kwargs.get('search_opts_tenant', {}))
        image_resource = self.cloud.resources[utl.IMAGE_RESOURCE]
        images_info = image_resource.read_info(**search_opts)
        return {'images_info': images_info}
