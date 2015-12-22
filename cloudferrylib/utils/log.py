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
from logging import handlers
import datetime
import os

import yaml

import cfglib

getLogger = logging.getLogger


def configure_logging():
    """Configure the logging

    Loading logging configuration file which is defined in the general
    configuration file and configure the logging sytem.
    Setting the level of console handler to DEBUG mode if debug option is set
    as True.
    """
    with open(cfglib.CONF.migrate.log_config, 'r') as f:
        config.dictConfig(yaml.load(f))
    if cfglib.CONF.migrate.debug:
        logger = logging.getLogger()
        for handler in logger.handlers:
            if handler.name == 'console':
                handler.setLevel(logging.DEBUG)
                break


class RunRotatingFileHandler(handlers.RotatingFileHandler):
    """Handler for logging to switch the logging file every run.

    The handler allows to include the scenario and the current datetime into
    the filename.

    :param filename: The template for filename
    :param date_format: The temaplate for formatting the current datetime
    """
    def __init__(self,
                 filename='%(scenario)s-%(date)s.log',
                 date_format='%F-%H-%M-%S',
                 **kwargs):
        self.date_format = date_format

        super(RunRotatingFileHandler, self).__init__(
                filename=self.get_filename(filename), **kwargs)

    def get_filename(self, filename):
        """Format the filename

        :param filename: the formatting string for the filename
        :return: Formatted filename with included scenarion and
        current datetime.
        """
        scenario = os.path.splitext(os.path.basename(
                cfglib.CONF.migrate.scenario))[0]
        dt = datetime.datetime.now().strftime(self.date_format)
        return filename % {
            'scenario': scenario,
            'date': dt
        }
