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

SRC = "src"
DST = "dst"


class Cloud(object):

    def __init__(self, resources, position):
        self.resources = resources

    def auth(self, config):
        identity = self.resources['identity']
        # Do we need here identity.auth()? We do authorization, when
        # instantiate this resource in the implementation (f.e. in os2os)
        for resource in self.resources:
            if resource != 'identity':
                self.resources[resource].auth(config, identity)
