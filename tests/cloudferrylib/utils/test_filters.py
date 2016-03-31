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
import datetime

from cloudferrylib.utils import filters
from tests import test


class BaseCFFiltersTestCase(test.TestCase):
    def test_base_class_has_get_filters_method(self):
        self.assertTrue(callable(filters.CFFilters.get_filters))

    def test_cannot_create_object_of_filters(self):
        self.assertRaises(TypeError, filters.CFFilters)


class FilterYamlTestCase(test.TestCase):
    @mock.patch("cloudferrylib.utils.filters.yaml.load")
    def test_reads_config_on_first_use(self, yaml_load):
        fy_stream = mock.Mock()
        fy = filters.FilterYaml(fy_stream)
        self.assertFalse(yaml_load.called)

        fy.get_filter_yaml()
        self.assertTrue(yaml_load.called)

    def test_returns_empty_dict_if_filter_conf_is_empty(self):
        filters_file = u""
        fy = filters.FilterYaml(filters_file)
        self.assertEqual(dict(), fy.get_filter_yaml())

    def test_returns_none_if_no_tenant_provided(self):
        filters_file = u""
        fy = filters.FilterYaml(filters_file)
        self.assertIsNone(fy.get_tenant())

    def test_returns_empty_list_if_nothing_in_image_ids(self):
        filters_file = u""
        fy = filters.FilterYaml(filters_file)
        self.assertEqual(list(), fy.get_image_ids())

    def test_returns_empty_list_for_get_excluded_image_ids(self):
        filters_file = u""
        fy = filters.FilterYaml(filters_file)
        self.assertEqual(list(), fy.get_excluded_image_ids())

    def test_returns_empty_list_if_nothing_in_instance_ids(self):
        filters_file = u""
        fy = filters.FilterYaml(filters_file)
        self.assertEqual(list(), fy.get_instance_ids())

    def test_returns_tenant_id_if_provided(self):
        tenant_id = 'some-tenant'
        filters_file = u"""
        tenants:
            tenant_id:
                - {tenant_id}
        """.format(tenant_id=tenant_id)
        fy = filters.FilterYaml(filters_file)
        self.assertEqual(tenant_id, fy.get_tenant())

    def test_returns_instances_from_instance_ids(self):
        instance1 = 'inst1'
        instance2 = 'inst2'
        filters_file = u"""
        instances:
            id:
                - {instance1}
                - {instance2}
        """.format(instance1=instance1, instance2=instance2)

        fy = filters.FilterYaml(filters_file)
        filtered_instances = fy.get_instance_ids()

        self.assertTrue(isinstance(filtered_instances, list))
        self.assertIn(instance1, filtered_instances)
        self.assertIn(instance2, filtered_instances)

    def test_returns_images_from_excluded_image_ids(self):
        image1 = 'image1'
        image2 = 'image2'
        filters_file = u"""
        images:
            exclude_images_list:
                - {image1}
                - {image2}
        """.format(image1=image1, image2=image2)

        fy = filters.FilterYaml(filters_file)
        filtered_images = fy.get_excluded_image_ids()

        self.assertTrue(isinstance(filtered_images, list))
        self.assertIn(image1, filtered_images)
        self.assertIn(image2, filtered_images)

    def test_returns_images_from_image_ids(self):
        image1 = 'image1'
        image2 = 'image2'
        filters_file = u"""
        images:
            images_list:
                - {image1}
                - {image2}
        """.format(image1=image1, image2=image2)

        fy = filters.FilterYaml(filters_file)
        filtered_images = fy.get_image_ids()

        self.assertTrue(isinstance(filtered_images, list))
        self.assertIn(image1, filtered_images)
        self.assertIn(image2, filtered_images)

    def test_date_returns_none_if_not_specified(self):
        filters_file = u""
        fy = filters.FilterYaml(filters_file)
        self.assertIsNone(fy.get_image_date())

    def test_date_filter_returns_datetime_object(self):
        filters_file = u"""
        images:
            date: 2000-01-01
        """

        fy = filters.FilterYaml(filters_file)

        filtered_date = fy.get_image_date()
        self.assertTrue(isinstance(filtered_date, datetime.date))
