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

"""Filters for Cinder volumes.

Filtering can be done by user through modifying filter config file. User can
specify filtered tenant ID and/or filtered volume ID. This module keeps logic
to filter cinder volumes based on user's input.

User can specify the following filtering options for volumes:
 - `date`:
   Filters volumes not older than date specified.
   DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
 - `volume_id`:
   Filters specified volume IDs;

Volumes filtering logic:
 - If nothing is specified in filters file all volumes MUST migrate;
 - If tenant is specified, ALL volumes which belong to this tenant MUST
   migrate;
 - If volumes' IDs are specified, only these volumes specified MUST migrate.

"""


import datetime

from cloudferrylib.utils import filters


DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def _filtering_disabled(elem):
    return elem is None or (isinstance(elem, list) and len(elem) == 0)


class CinderFilters(filters.CFFilters):

    """Build required filters based on filter configuration file."""

    def __init__(self, cinder_client, filter_yaml):
        super(CinderFilters, self).__init__(filter_yaml)
        self.cinder_client = cinder_client

    def get_filters(self):
        return [
            self.datetime_filter(),
            self.tenant_filter(),
            self.volume_id_filter(),
        ]

    def get_tenant_filter(self):
        return self.tenant_filter()

    def tenant_filter(self):
        tenant_id = self.filter_yaml.get_tenant()
        return lambda i: (_filtering_disabled(tenant_id) or
                          self.get_col(i, 'project_id') == tenant_id)

    def volume_id_filter(self):
        volumes = self.filter_yaml.get_volume_ids()
        return lambda i: (_filtering_disabled(volumes) or
                          self.get_col(i, 'id') in volumes)

    def datetime_filter(self):
        date = self.filter_yaml.get_volume_date()
        if isinstance(date, str):
            date = datetime.datetime.strptime(date, DATETIME_FMT)

        def _filter(vol):
            upd = self.get_col(vol, 'updated_at')
            if not upd:
                upd = self.get_col(vol, 'created_at')
            if isinstance(upd, str):
                upd = datetime.datetime.strptime(upd, DATETIME_FMT)
            return _filtering_disabled(date) or date <= upd
        return _filter

    @staticmethod
    def get_col(elem, col):
        atr = 'os-vol-tenant-attr:tenant_id' if col == 'project_id' else col
        return elem.get(col, None) \
            if isinstance(elem, dict) \
            else getattr(elem, atr, None)
