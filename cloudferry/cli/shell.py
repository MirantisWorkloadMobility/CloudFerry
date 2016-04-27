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

import argparse
import sys

from cliff import app
from cliff import commandmanager

import cloudferry


class CloudFerryApp(app.App):
    def __init__(self):
        super(CloudFerryApp, self).__init__(
            description="Openstack cloud workload migration tool",
            version=cloudferry.__version__,
            command_manager=commandmanager.CommandManager('cloudferry'),
            deferred_help=True,
        )

    def build_option_parser(self, description, version,
                            argparse_kwargs=None):
        argparse_kwargs = argparse_kwargs or {}
        parser = argparse.ArgumentParser(
            description=description,
            add_help=False,
            **argparse_kwargs
        )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s {0}'.format(version),
        )
        if self.deferred_help:
            parser.add_argument(
                '-h', '--help',
                dest='deferred_help',
                action='store_true',
                help="Show help message and exit.",
            )
        else:
            parser.add_argument(
                '-h', '--help',
                action=app.HelpAction,
                nargs=0,
                default=self,
                help="Show this help message and exit.",
            )
        parser.add_argument(
            '-d', '--debug',
            default=False,
            action='store_true',
            help='Show debug messages.',
        )
        return parser

    def configure_logging(self):
        pass


def main(argv=sys.argv[1:]):
    return CloudFerryApp().run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
