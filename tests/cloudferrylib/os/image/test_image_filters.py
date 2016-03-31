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

import datetime
from itertools import ifilter
import mock

from cloudferrylib.os.image import filters

from tests import test


DONT_CARE = mock.Mock()


def _image(uuid=DONT_CARE, tenant=DONT_CARE, is_public=True, update_time=None,
           status='active'):
    image = mock.Mock()
    image.is_public = is_public
    image.id = uuid
    image.owner = tenant
    image.updated_at = update_time
    image.status = status
    return image


class GlanceImageFilterTestCase(test.TestCase):
    def apply_filter(self, images, expected_ids, tenant, image_ids,
                     exclude_image_ids=None, date=None,
                     glance_client=mock.MagicMock()):
        filter_yaml = mock.Mock()
        filter_yaml.get_tenant.return_value = tenant
        filter_yaml.get_image_ids.return_value = image_ids
        if exclude_image_ids:
            filter_yaml.get_excluded_image_ids.return_value = exclude_image_ids
        else:
            filter_yaml.get_excluded_image_ids.return_value = []

        filter_yaml.get_image_date.return_value = date
        filter_yaml.is_public_and_member_images_filtered.return_value = False

        glance_filters = filters.GlanceFilters(glance_client=glance_client,
                                               filter_yaml=filter_yaml)

        for f in glance_filters.get_filters():
            images = ifilter(f, images)

        self.assertEqual(set(expected_ids),
                         set([i.id for i in images]))

    def test_public_images_are_always_kept(self):
        images = [_image('private', 'Foo', False),
                  _image('pub', 'Bar', True)]

        expected_ids = ['pub']

        self.apply_filter(images, expected_ids, 'Some_tenant', [])

    def test_keeps_private_image_if_filtered_image_ids_not_set(self):
        images = [_image('private', 'Foo', False),
                  _image('private_bad', 'Bar', False),
                  _image('pub', 'Bar', True)]

        expected_ids = ['pub', 'private']

        self.apply_filter(images, expected_ids, 'Foo', [])

    def test_image_not_filtered_if_not_belongs_to_filtered_tenant(self):
        images = [_image('private', 'Foo', False),
                  _image('private_bad', 'Bar', False),
                  _image('pub', 'Bar', True)]

        expected_ids = ['pub', 'private']
        ids_filter = ['private', 'private_bad']

        self.apply_filter(images, expected_ids, 'Foo', ids_filter)

    def test_keep_all_for_empty_filter(self):
        images = [_image('private', 'Foo', False),
                  _image('private2', 'Bar', False),
                  _image('pub', 'Bar', True)]

        expected_ids = ['pub', 'private', 'private2']

        self.apply_filter(images, expected_ids, None, [])

    def test_date(self):
        images = [_image('private', 'Foo', False, '2000-01-06T00:00:00'),
                  _image('private_old', 'Foo', False, '2000-01-01T00:00:00'),
                  _image('private2', 'Bar', False, '2000-01-06T00:00:00'),
                  _image('pub', 'Bar', True, '2000-01-01T00:00:00')]

        expected_ids = ['pub', 'private', 'private2']
        filter_date = datetime.datetime.strptime('2000-01-05T00:00:00',
                                                 "%Y-%m-%dT%H:%M:%S")
        self.apply_filter(images, expected_ids, None, [], date=filter_date)

    def test_date_with_tenant(self):
        images = [_image('private', 'Foo', False, '2000-01-06T00:00:00'),
                  _image('private_old', 'Foo', False, '2000-01-01T00:00:00'),
                  _image('private2', 'Bar', False, '2000-01-06T00:00:00'),
                  _image('pub', 'Bar', True, '2000-01-01T00:00:00')]

        expected_ids = ['pub', 'private']
        filter_date = datetime.datetime.strptime('2000-01-05T00:00:00',
                                                 "%Y-%m-%dT%H:%M:%S")
        self.apply_filter(images, expected_ids, 'Foo', [], date=filter_date)

    def test_members(self):
        images = [_image('private', 'Foo', False),
                  _image('private_bad', 'Bar', False),
                  _image('shared', 'Bar', False),
                  _image('pub', 'Bar', True)]

        expected_ids = ['pub', 'private', 'shared']

        glance_client = mock.Mock()
        image_members = mock.Mock()
        image_member = mock.Mock()
        image_member.image_id = 'shared'
        image_members.list.return_value = [image_member]
        glance_client.image_members = image_members

        self.apply_filter(images, expected_ids, 'Foo', [],
                          glance_client=glance_client)

    def test_statuses(self):
        images = [_image(uuid='private', status='queued'),
                  _image(uuid='private_1', status='active'),
                  _image(uuid='shared', status='saving'),
                  _image(uuid='pub', status='active'),
                  _image(uuid='private_old', status='deleted'),
                  _image(uuid='private_new', status='killed'),
                  _image(uuid='private_bad', status='pending_delete'),
                  ]

        expected_ids = ['private_1', 'pub']

        self.apply_filter(images, expected_ids, None, [])

    def test_exclude_images(self):
        images = [_image(uuid='image1', tenant='foo', is_public=False),
                  _image(uuid='image2', tenant='foo', is_public=False),
                  _image(uuid='image3', tenant='bar', is_public=False),
                  _image(uuid='image4', tenant='bar', is_public=False),
                  _image(uuid='image5', tenant='bar', is_public=True),
                  ]

        exclude_image_ids = ['image1', 'image3']
        expected_ids = ['image2', 'image4', 'image5']

        self.apply_filter(images, expected_ids, None, [],
                          exclude_image_ids=exclude_image_ids)
