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

import datetime
import logging
from logging import config
from logging import handlers
import os
import sys

from fabric import api
import yaml

import cfglib
from cloudferrylib.utils import sizeof_format

getLogger = logging.getLogger


class StdoutLogger(object):
    """ The wrapper of stdout messages
    Transfer all messages from stdout to cloudferrylib.stdout logger.

    """
    def __init__(self, name=None):
        self.log = logging.getLogger(name or 'cloudferrylib.stdout')

    def write(self, message):
        message = message.strip()
        if message:
            self.log.info(message)

    def flush(self):
        pass


def configure_logging():
    """Configure the logging

    Loading logging configuration file which is defined in the general
    configuration file and configure the logging system.
    Setting the level of console handler to DEBUG mode if debug option is set
    as True.
    Wrap the stdout stream by StdoutLogger.
    """
    with open(cfglib.CONF.migrate.log_config, 'r') as f:
        config.dictConfig(yaml.load(f))
    if cfglib.CONF.migrate.debug:
        logger = logging.getLogger('cloudferrylib')
        for handler in logger.handlers:
            if handler.name == 'console':
                handler.setLevel(logging.DEBUG)
    sys.stdout = StdoutLogger()


class RunRotatingFileHandler(handlers.RotatingFileHandler):
    """Handler for logging to switch the logging file every run.

    The handler allows to include the scenario and the current datetime into
    the filename.

    :param filename: The template for filename
    :param date_format: The template for formatting the current datetime
    """
    def __init__(self,
                 filename='%(scenario)s-%(date)s.log',
                 date_format='%F-%H-%M-%S',
                 **kwargs):
        self.date_format = date_format
        max_bytes = sizeof_format.parse_size(kwargs.pop('maxBytes', 0))

        super(RunRotatingFileHandler, self).__init__(
            filename=self.get_filename(filename),
            maxBytes=max_bytes,
            **kwargs)

    def get_filename(self, filename):
        """Format the filename

        :param filename: the formatting string for the filename
        :return: Formatted filename with included scenario and
        current datetime.
        """
        scenario = os.path.splitext(os.path.basename(
            cfglib.CONF.migrate.scenario))[0]
        dt = datetime.datetime.now().strftime(self.date_format)
        return filename % {
            'scenario': scenario,
            'date': dt
        }


class CurrentTaskFilter(logging.Filter):
    """Define the current_task variable for the log messages.

    :param name_format: The format of current task name.
    Default value is %(name)s
    """

    def __init__(self, name_format='%(name)s', **kwargs):
        super(CurrentTaskFilter, self).__init__(**kwargs)
        self.name_format = name_format

    def filter(self, record):
        current_task = self.name_format % {
            'name': api.env.current_task or '<NoTask>',
        }
        record.current_task = current_task
        return True
