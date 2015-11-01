#!/usr/bin/env python
# Copyright (c) 2015 Mirantis Inc.
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
import shutil
from pkg_resources import Requirement, resource_filename

import fabfile


def migrate_run(args):
    fabfile.migrate(args.config, args.debug)


def migrate_args(parser):
    parser.add_argument('config')
    parser.add_argument('-d', '--debug', action='store_true')


def evacuate_run(args):
    fabfile.evacuate(args.config, args.debug, args.iteration)


def evacuate_args(parser):
    parser.add_argument('config')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-i', '--iteration', action='store_true')


def condense_run(args):
    fabfile.condense(args.config, args.vm_grouping_config, args.debug)


def condense_args(parser):
    parser.add_argument('config')
    parser.add_argument('vm_grouping_config')
    parser.add_argument('-d', '--debug', action='store_true')


def init(args):
    install_folder = resource_filename(Requirement.parse("CloudFerry"), './')
    ignore_py = shutil.ignore_patterns('*.py', '*.pyc')

    def copy(folder):
        shutil.copytree("%s/%s" % (install_folder, folder), "./%s" % folder,
                        False, ignore_py)

    copy('configs')
    copy('scenario')
    copy('templates')


class Command(object):
    def __init__(self, name, help, run_func, init_args_func=None):
        self.name = name
        self.help = help
        self.init_args_func = init_args_func
        self.run_func = run_func

    def init_argparse(self, subparsers):
        parser = subparsers.add_parser(self.name, help=self.help)
        if self.init_args_func:
            self.init_args_func(parser)
        parser.set_defaults(func=self.run_func)


def console():
    commands = [Command('migrate', "Doing actual migration. You must provide "
                                   "path to config yaml-file.",
                        migrate_run, migrate_args),
                Command('evacuate', "Doing migration in source cloud to free "
                                    "computes. You must run condense first.",
                        evacuate_run, evacuate_args),
                Command('condense', "Collect info about source cloud. Needed "
                                    "for evacuate action.",
                        condense_run, condense_args),
                Command('init', "Create sample environment (config, scenarios "
                                "and tasks definition) in current folder.",
                        init)]
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    for command in commands:
        command.init_argparse(subparsers)
    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()
