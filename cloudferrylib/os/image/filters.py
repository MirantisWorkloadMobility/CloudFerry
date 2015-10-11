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

"""Filters for Glance images.

Filtering can be done by user through modifying filter config file. User can
specify filtered tenant ID and/or filtered image ID. This module keeps logic to
filter glance images based on user's input.

User can specify the following filtering options for images:
 - `date`:
   Filters images not older than date specified. Other filters are ignored in
   this case;
 - `image_id`:
   Filters specified image IDs;
 - `image_name`:
   FIXME: image names are not unique.
   Filters specified image names.

Images filtering logic:
 - Public images:
    - MUST migrate regardless of filters config contents;
 - Private images:
    - If nothing is specified in filters file all private images MUST migrate;
    - If tenant is specified, ALL images which belong to this tenant MUST
      migrate;
    - If image ID is specified, only images specified MUST migrate.
"""
import datetime

from cloudferrylib.utils import filters


def _tenant_filtering_enabled(filtered_tenant_id):
    return filtered_tenant_id is not None


def _tenant_filtering_disabled(filtered_tenant_id):
    return not _tenant_filtering_enabled(filtered_tenant_id)


def _image_filtering_enabled(filtered_images):
    return filtered_images is not None and len(filtered_images) > 0


def _image_filtering_disabled(filtered_images):
    return not _image_filtering_enabled(filtered_images)


def tenant_filter(filtered_tenant_id):
    """Filters images not specified in tenant_id section of filters file"""
    return lambda i: (i.is_public or
                      _tenant_filtering_disabled(filtered_tenant_id) or
                      (_tenant_filtering_enabled(filtered_tenant_id) and
                          i.owner == filtered_tenant_id))


def image_id_filter(filtered_images):
    """Filters images not specified in image_ids section of filters file"""
    return lambda i: (i.is_public or
                      _image_filtering_disabled(filtered_images) or
                      (_image_filtering_enabled(filtered_images) and
                          i.id in filtered_images))


def member_filter(glance_client, filtered_tenant_id):
    """Filters images which are shared between multiple tenants using image
    membership feature (see `glance help member-list`)"""
    members_present = len(glance_client.image_members.list(
        member=filtered_tenant_id)) > 0
    return lambda i: (
        i.is_public or
        _tenant_filtering_disabled(filtered_tenant_id) or
        not members_present or
        _tenant_filtering_enabled(filtered_tenant_id) and
        i.owner in glance_client.image_members.list(image=i,
                                                    member=filtered_tenant_id))


def datetime_filter(filtered_tenant_id, date):
    """Filters images not older than :arg date:"""
    return lambda i: (
        i.is_public or
        i.is_snapshot or
        _tenant_filtering_disabled(filtered_tenant_id) and
        date <= datetime.datetime.strptime(i.updated_at, "%Y-%m-%dT%H:%M:%S"))


class GlanceFilters(filters.CFFilters):
    """Builds required filters based on filter configuration file"""

    def __init__(self, glance_client, filter_yaml):
        super(GlanceFilters, self).__init__(filter_yaml)
        self.glance_client = glance_client

    def get_filters(self):
        if self.filter_yaml.get_image_date() is not None:
            return [
                datetime_filter(self.filter_yaml.get_tenant(),
                                self.filter_yaml.get_image_date())
            ]

        return [
            member_filter(self.glance_client,
                          self.filter_yaml.get_tenant()),
            tenant_filter(self.filter_yaml.get_tenant()),
            image_id_filter(self.filter_yaml.get_image_ids())
        ]
