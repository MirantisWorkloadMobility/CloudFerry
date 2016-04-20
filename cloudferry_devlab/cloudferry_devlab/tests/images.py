# Copyright 2015 Mirantis Inc.
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

from cloudferry_devlab.tests import test_exceptions


class Blacklisted(object):

    def __init__(self, config, glanceclient):
        self.config = config
        self.glanceclient = glanceclient

    def get_blacklisted_img_ids(self):
        """Get Blacklisted Image IDs."""

        blacklisted_img_ids = []
        try:
            blacklisted_img_ids = [self._get_image_id(img)
                                   for img in self.config.images_blacklisted]
        except test_exceptions.NotFound:
            pass
        return blacklisted_img_ids

    def _get_image_id(self, image_name):
        for image in self.glanceclient.images.list():
            if image.name == image_name:
                return image.id
        raise test_exceptions.NotFound('Image with name "%s" was not found'
                                       % image_name)

    def filter_images(self):
        img_list = [x.__dict__['id'] for x in
                    self.glanceclient.images.list(search_opts={
                        'is_public': False})]
        exclude_img_ids = self.get_blacklisted_img_ids()
        included_img_ids = [img for img in img_list
                            if img not in exclude_img_ids]
        return included_img_ids
