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

from cloudferry.lib.base.action import action
from cloudferry.lib.utils import utils


class GetFilter(action.Action):

    def run(self, **kwargs):
        search_opts, search_opts_img, search_opts_tenant = {}, {}, {}
        search_opts_vol = {}
        filter_path = self.cfg.migrate.filter_path

        if (utils.read_yaml_file(filter_path) and
                not self.cfg.migrate.migrate_whole_cloud):
            filter_config = utils.read_yaml_file(filter_path)
            if utils.INSTANCES_TYPE in filter_config:
                search_opts = filter_config[utils.INSTANCES_TYPE]
            if utils.IMAGES_TYPE in filter_config:
                search_opts_img = filter_config[utils.IMAGES_TYPE]
            if utils.VOLUMES_TYPE in filter_config:
                search_opts_vol = filter_config[utils.VOLUMES_TYPE]
            if utils.TENANTS_TYPE in filter_config:
                search_opts_tenant = filter_config[utils.TENANTS_TYPE]

        return {
            'search_opts': search_opts,
            'search_opts_img': search_opts_img,
            'search_opts_vol': search_opts_vol,
            'search_opts_tenant': search_opts_tenant
        }
