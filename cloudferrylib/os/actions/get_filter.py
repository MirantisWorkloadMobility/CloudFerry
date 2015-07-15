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


class GetFilter(action.Action):

    def run(self, **kwargs):
        search_opts, search_opts_img, search_opts_tenant = None, {}, {}
        filter_path = self.cfg.migrate.filter_path
        if utl.read_yaml_file(filter_path):
            filter_config = utl.read_yaml_file(filter_path)
            if utl.INSTANCES_TYPE in filter_config:
                search_opts = filter_config[utl.INSTANCES_TYPE]
            if utl.IMAGES_TYPE in filter_config:
                search_opts_img = filter_config[utl.IMAGES_TYPE]
            if utl.TENANTS_TYPE in filter_config:
                search_opts_tenant = filter_config[utl.TENANTS_TYPE]
        return {
            'search_opts': search_opts,
            'search_opts_img': search_opts_img,
            'search_opts_tenant': search_opts_tenant
        }
