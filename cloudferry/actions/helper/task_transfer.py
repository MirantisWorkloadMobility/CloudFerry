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

import logging

from cloudferry.lib.base.action import action
from cloudferry.lib.copy_engines import base
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)


class TaskTransfer(action.Action):
    def __init__(self, init,
                 driver=None,
                 input_info='info',
                 resource_name=utils.VOLUMES_TYPE,
                 resource_root_name=utils.VOLUME_BODY):
        super(TaskTransfer, self).__init__(init)
        self.driver = base.get_copier(self.src_cloud, self.dst_cloud, driver)
        self.resource_name = resource_name
        self.resource_root_name = resource_root_name
        self.input_info = input_info

    def run(self, **kwargs):
        info = kwargs[self.input_info]
        data_for_trans = info[self.resource_name]

        for item in data_for_trans.itervalues():
            data = item[self.resource_root_name]

            data_is_invalid = not all([data.get(k)
                                       for k in ('path_src', 'path_dst',
                                                 'host_src', 'host_dst')])

            if data_is_invalid:
                LOG.warning("Cannot copy from %s:%s to %s:%s - source or "
                            "destination path definition is invalid.",
                            data.get('host_src'), data.get('path_src'),
                            data.get('host_dst'), data.get('path_dst'))
                continue

            if self.driver.check_usage(data):
                self.driver.transfer(data)

        return {}
