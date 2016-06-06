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
from cloudferry.cloud import os2os
from cloudferry.lib.scheduler import scenario
from cloudferry.lib.utils import errorcodes
from cloudferry.lib.utils import utils

LOG = logging.getLogger(__name__)
env.forward_agent = True


class Migrate(base.ConfigMixin, command.Command):
    """Running migration v.1"""

    def get_parser(self, prog_name):
        parser = super(Migrate, self).get_parser(prog_name)

        parser.add_argument('-s', '--scenario', default=None,
                            help='Path to a scenario file.')
        parser.add_argument('-f', '--filter-path', default=None,
                            help='Path to the filter file.')
        parser.add_argument('-c', '--copy-backend', default=None,
                            choices=('rsync', 'scp', 'bbcp'),
                            help='Copy backend.')
        return parser

    def override_config(self, group, **kwargs):
        for name, value in kwargs.items():
            if value is not None:
                self.config.set_override(name, value, group)

    def take_action(self, parsed_args):
        self.override_config('migrate',
                             scenario=parsed_args.scenario,
                             filter_path=parsed_args.filter_path,
                             copy_backend=parsed_args.copy_backend)
        self.config.log_opt_values(LOG, logging.DEBUG)
        filters = utils.read_yaml_file(self.config.migrate.filter_path)
        LOG.debug('Filters: %s', pprint.pformat(filters))
        env.key_filename = self.config.migrate.key_filename
        env.connection_attempts = self.config.migrate.ssh_connection_attempts
        env.cloud = os2os.OS2OSFerry(self.config)
        status_error = env.cloud.migrate(scenario.Scenario(
            path_scenario=self.config.migrate.scenario,
            path_tasks=self.config.migrate.tasks_mapping))
        if status_error != errorcodes.NO_ERROR:
            raise RuntimeError("Migration failed")
