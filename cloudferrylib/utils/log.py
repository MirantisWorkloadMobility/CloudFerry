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

import logging
from logging import config

import yaml

import cfglib

getLogger = logging.getLogger


def configure_logging():
    with open(cfglib.CONF.migrate.log_config, 'r') as f:
        config.dictConfig(yaml.load(f))
    if cfglib.CONF.migrate.debug:
        logger = logging.getLogger()
        for handler in logger.handlers:
            if handler.name == 'console':
                handler.setLevel(logging.DEBUG)
                break
