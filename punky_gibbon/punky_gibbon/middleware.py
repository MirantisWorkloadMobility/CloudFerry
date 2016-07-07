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
import json
import logging
import random

LOG = logging.getLogger(__name__)
DEFAULT_MESSAGE = 'Punky Gibbon is not in a mood to serve your request'


class PunkyGibbon(object):
    def __init__(self, app, global_conf, random_chance=0.5, ignore_ips='',
                 message=None, detailed_message=None, **kwargs):
        # pylint: disable=unused-argument
        self.app = app
        self.global_conf = global_conf
        self.random_chance = float(random_chance)
        self.message = message or DEFAULT_MESSAGE
        self.detailed_message = detailed_message or DEFAULT_MESSAGE
        self.ignore_ips = [ip.strip() for ip in ignore_ips.split(',')]

    def __call__(self, environ, start_response):
        if self.should_fail(environ):
            start_response('500 Internal Server Error',
                           [('Content-type', 'application/json')])
            return [json.dumps({
                "error": {
                    'message': self.message,
                    'details': self.detailed_message,
                }
            })]
        else:
            return self.app(environ, start_response)

    def should_fail(self, environ):
        if environ['REMOTE_ADDR'] in self.ignore_ips:
            return False
        return random.random() < self.random_chance
