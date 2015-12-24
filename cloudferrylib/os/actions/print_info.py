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
import pprint

from fabric import api

import cfglib
from cloudferrylib.base.action import action
from cloudferrylib.utils import log
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)


class PrintConfiguration(action.Action):
    def run(self, **kwargs):
        cfglib.CONF.log_opt_values(LOG, logging.INFO)


class PrintScenario(action.Action):
    def run(self, **kwargs):
        cloud = api.env.cloud
        if cloud is not None and cloud.scenario:
            LOG.info('Scenario namespace: %s',
                     pprint.pformat(cloud.scenario.namespace))
            LOG.info('Scenario preparation: %s',
                     pprint.pformat(cloud.scenario.preparation))
            LOG.info('Scenario migration: %s',
                     pprint.pformat(cloud.scenario.migration))
            LOG.info('Scenario rollback: %s',
                     pprint.pformat(cloud.scenario.rollback))


class PrintFilter(action.Action):
    def __init__(self, init, raw=False):
        super(PrintFilter, self).__init__(init)
        self.raw = raw

    def _print_options(self, message, options):
        if options:
            LOG.info('%s: %s', message, pprint.pformat(options))

    def run(self, **kwargs):
        if self.raw:
            filters = utils.read_yaml_file(cfglib.CONF.migrate.filter_path)
            if filters:
                LOG.info('Filters: %s', pprint.pformat(filters))
        else:
            self._print_options('Filter by instances',
                                kwargs.get('search_opts', {}))
            self._print_options('Filter by images',
                                kwargs.get('search_opts_img', {}))
            self._print_options('Filter by volumes',
                                kwargs.get('search_opts_vol', {}))
            self._print_options('Filter by tenants',
                                kwargs.get('search_opts_tenant', {}))
