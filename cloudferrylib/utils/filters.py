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

import abc
import yaml


class FilterYaml(object):

    """Keeps contents of filter.yaml config file"""

    def __init__(self, filter_yaml_stream):
        self._file = filter_yaml_stream
        self._filter_yaml = None

    def read(self):
        self._filter_yaml = yaml.load(self._file) or {}
        return self._filter_yaml

    def get_filter_yaml(self):
        if self._filter_yaml is None:
            self.read()
        return self._filter_yaml

    def get_tenant(self):
        fy = self.get_filter_yaml()
        tenants = fy.get('tenants', {})
        return tenants.get('tenant_id', [None])[0]

    def get_image_ids(self):
        fy = self.get_filter_yaml()
        images = fy.get('images', {})
        return images.get('images_list', [])

    def get_excluded_image_ids(self):
        fy = self.get_filter_yaml()
        images = fy.get('images', {})
        return images.get('exclude_images_list', [])

    def is_public_and_member_images_filtered(self):
        fy = self.get_filter_yaml()
        images = fy.get('images', {})
        return images.get(
            'dont_include_public_and_members_from_other_tenants', True)

    def get_volume_ids(self):
        fy = self.get_filter_yaml()
        volumes = fy.get('volumes', {})
        return volumes.get('volumes_list', [])

    def get_instance_ids(self):
        fy = self.get_filter_yaml()
        instances = fy.get('instances', {})
        return instances.get('id', [])

    def get_image_date(self):
        # TODO: verify date filtering original functionality
        fy = self.get_filter_yaml()
        images = fy.get('images', {})
        return images.get('date')

    def get_volume_date(self):
        # TODO: verify date filtering original functionality
        fy = self.get_filter_yaml()
        volumes = fy.get('volumes', {})
        return volumes.get('date')


class CFFilters(object):
    """Base class for filter methods"""

    __metaclass__ = abc.ABCMeta

    def __init__(self, filter_yaml):
        """
        :arg filter_yaml: `FilterYaml` object
        """
        self.filter_yaml = filter_yaml

    @abc.abstractmethod
    def get_filters(self):
        """Returns list of callable objects which can be supplied to a
        standard filter() method."""

        raise NotImplementedError()
