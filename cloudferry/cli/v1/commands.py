# Copyright (c) 2016 Mirantis Inc.
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

from fabric.api import env
from cliff import command

from cloudferry.cli import base
from cloudferry.cloud import cloud_ferry
from cloudferry.lib.scheduler import scenario
from cloudferry.lib.utils import errorcodes
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)
env.forward_agent = True


class Migrate(base.ConfigMixin, command.Command):
    """Running migration v.1"""

    def take_action(self, parsed_args):
        self.config.log_opt_values(LOG, logging.DEBUG)
        filters = utils.read_yaml_file(self.config.migrate.filter_path)
        LOG.debug('Filters: %s', pprint.pformat(filters))
        env.key_filename = self.config.migrate.key_filename
        env.connection_attempts = self.config.migrate.ssh_connection_attempts
        cloud = cloud_ferry.CloudFerry(self.config)
        status_error = cloud.migrate(scenario.Scenario(
            path_scenario=self.config.migrate.scenario,
            path_tasks=self.config.migrate.tasks_mapping))
        if status_error != errorcodes.NO_ERROR:
            raise RuntimeError("Migration has been failed")
