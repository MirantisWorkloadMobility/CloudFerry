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

import importlib


class CloudFerry(object):
    def __new__(cls, config):
        if cls != CloudFerry:
            # Call is already for a subclass, so pass it through
            return super(CloudFerry, cls).__new__(cls)

        if (config.src.type == 'os') and (config.dst.type == 'os'):
            # Maybe it is better to provide new param in config such as
            # 'migration_type'? Or as Alex mentioned, make smth like paste.ini?
            # And specify it there for first time? It can be directly names of
            # classes or any human readable mapping. And later some day
            # implement smth like auto discovering, if it will be needed
            os2os = importlib.import_module('cloud.os2os')
            return os2os.OS2OSFerry(config)

        return super(CloudFerry, cls).__new__(cls)

    def __init__(self, config):
        self.config = config

    def migrate(self, scenario=None):
        pass
