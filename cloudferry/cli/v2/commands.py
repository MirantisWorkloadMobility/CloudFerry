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

from cliff import command
from cliff import lister

from cloudferry.cli import base
from cloudferry.lib import stage
from cloudferry.lib.os.discovery import model
from cloudferry.lib.os.estimation import procedures
from cloudferry.lib.os.migrate import base as migrate_base
from cloudferry.lib.utils import taskflow_utils

# Importing of these modules is necessary to fill model.type_aliases variable
# pylint: disable=unused-import
from cloudferry.lib.os.discovery import keystone, nova, cinder, glance  # noqa


class Discover(base.YamlConfigMixin, command.Command):
    def take_action(self, parsed_args):
        stage.execute_stage('cloudferry.lib.os.discovery.stages.DiscoverStage',
                            self.config, force=True)


class Link(base.YamlConfigMixin, command.Command):
    def take_action(self, parsed_args):
        stage.execute_stage('cloudferry.lib.os.discovery.stages.LinkStage',
                            self.config, force=True)


class MigrationBaseMixin(base.YamlConfigMixin):
    def get_parser(self, prog_name):
        parser = super(MigrationBaseMixin, self).get_parser(prog_name)
        parser.add_argument('migration', help='Name of migration is defined '
                                              'in the configuration file.')
        return parser

    def take_action(self, parsed_args):
        if parsed_args.migration not in self.config.migrations:
            self.app.parser.error(
                "Invalid migration: '%s' (choose from %s)" % (
                    parsed_args.migration,
                    "'" + "', ".join(self.config.migrations.keys()) + "'"))


class EstimateMigration(MigrationBaseMixin, lister.Lister):
    """Estimate migration.

    Returns list of number and size of objects to be migrated.
    """
    def take_action(self, parsed_args):
        super(EstimateMigration, self).take_action(parsed_args)

        stage.execute_stage('cloudferry.lib.os.discovery.stages.LinkStage',
                            self.config)
        pr = procedures.EstimateCopy(self.config, parsed_args.migration)
        return ('Type', 'Count', 'Size'), pr.run()


class ShowObjects(MigrationBaseMixin, lister.Lister):
    """Show objects of migration.

    Return list of objects.
    """
    def get_parser(self, prog_name):
        parser = super(ShowObjects, self).get_parser(prog_name)
        parser.add_argument('-l', '--limit', default=None, type=int,
                            help="Number of largest objects")
        parser.add_argument('-u', '--show-unused', default=False,
                            action='store_true',
                            help='Show unused objects.')
        parser.add_argument('-o', '--object', dest='filters',
                            action='append', default=[],
                            choices=procedures.ShowObjects.FILTERS,
                            help='Type of objects')
        return parser

    def take_action(self, parsed_args):
        super(ShowObjects, self).take_action(parsed_args)

        stage.execute_stage('cloudferry.lib.os.discovery.stages.LinkStage',
                            self.config)

        pr = procedures.ShowObjects(
            self.config, parsed_args.migration, parsed_args.filters,
            parsed_args.show_unused, parsed_args.limit)
        data = pr.run()
        return ('Type', 'ID', 'Name', 'Size'), data


class Query(base.YamlConfigMixin, lister.Lister):
    """Show objects of cloud"""
    def get_parser(self, prog_name):
        parser = super(Query, self).get_parser(prog_name)
        parser.add_argument('cloud', help="Name of cloud")
        parser.add_argument('object_type',
                            choices=procedures.model.type_aliases.keys(),
                            help='Type of object')
        parser.add_argument('query', default='[*]', nargs='?',
                            help='JMESPath query')
        return parser

    def take_action(self, parsed_args):
        if parsed_args.cloud not in self.config.clouds:
            self.app.parser.error(
                "Invalid cloud: '%s' (choose from %s)" % (
                    parsed_args.cloud,
                    "'" + "', ".join(self.config.clouds.keys()) + "'"))

        return procedures.show_query(parsed_args.cloud,
                                     parsed_args.object_type,
                                     parsed_args.query)


class Migrate(MigrationBaseMixin, command.Command):
    """Running migration v.2"""

    def take_action(self, parsed_args):
        super(Migrate, self).take_action(parsed_args)

        stage.execute_stage('cloudferry.lib.os.discovery.stages.LinkStage',
                            self.config)

        with model.Session() as session:
            migration = self.config.migrations[parsed_args.name]
            objects = migration.query.search(session, migration.source)
            graph = taskflow_utils.create_graph_flow(
                parsed_args.name, objects, migrate_base.create_migration_flow,
                self.config, migration)

        taskflow_utils.execute_flow(graph)
