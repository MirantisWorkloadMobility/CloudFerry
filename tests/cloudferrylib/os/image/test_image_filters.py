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

import mock
from cloudferrylib.os.image import filters

from tests import test


DONT_CARE = mock.Mock()


def _image(uuid=DONT_CARE, tenant=DONT_CARE, is_public=True):
    image = mock.Mock()
    image.is_public = is_public
    image.id = uuid
    image.owner = tenant
    return image


class GlanceImageFilterTestCase(test.TestCase):
    def test_public_images_are_always_kept(self):
        num_public = 10
        num_private = 5

        images = (_image(is_public=i < num_public)
                  for i in xrange(num_public + num_private))

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = "some-other-tenant"
        filter_yaml.get_image_ids.return_value = []
        filter_yaml.get_image_date.return_value = None

        glance_filters = filters.GlanceFilters(glance_client=mock.MagicMock(),
                                               filter_yaml=filter_yaml)

        fs = glance_filters.get_filters()

        for f in fs:
            images = filter(f, images)

        self.assertEqual(len(images), num_public)

    def test_keeps_private_image_if_filtered_image_ids_not_set(self):
        num_private = 5
        num_public = 10
        total = num_private + num_public
        expected_ids = (i for i in xrange(num_private))
        images = [_image(is_public=False, uuid=i) for i in expected_ids]
        images.extend([_image(is_public=True, uuid=i)
                       for i in xrange(num_private, total)])

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = None
        filter_yaml.get_image_ids.return_value = []
        filter_yaml.get_image_date.return_value = None

        glance_filters = filters.GlanceFilters(glance_client=mock.MagicMock(),
                                               filter_yaml=filter_yaml)

        fs = glance_filters.get_filters()

        for f in fs:
            images = filter(f, images)

        self.assertEqual(len(images), total)
        self.assertTrue([i.id in expected_ids for i in images])

    def test_image_not_filtered_if_not_belongs_to_filtered_tenant(self):
        t1_image_id = 't1_image_id'
        t2_image_id = 't2_image_id'

        t1_image = _image(tenant="t1", uuid=t1_image_id, is_public=False)
        t2_image = _image(tenant="t2", uuid=t2_image_id, is_public=False)

        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = "some other tenant"
        filter_yaml.get_image_ids.return_value = []
        filter_yaml.get_image_date.return_value = None

        images = [t1_image, t2_image]

        glance_filters = filters.GlanceFilters(glance_client=mock.MagicMock(),
                                               filter_yaml=filter_yaml)
        fs = glance_filters.get_filters()

        for f in fs:
            images = filter(f, images)

        image_ids = [i.id for i in images]

        self.assertNotIn(t1_image_id, image_ids)
        self.assertNotIn(t2_image_id, image_ids)
