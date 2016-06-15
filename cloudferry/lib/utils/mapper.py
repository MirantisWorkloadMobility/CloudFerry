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
import os
import yaml

from cloudferry import cfglib

LOG = logging.getLogger(__name__)
CONF = cfglib.CONF


class Mapper(object):
    _config = None

    @classmethod
    def _load_configuration(cls):
        resource_map_file = CONF.migrate.resource_map
        if not os.path.exists(resource_map_file):
            cls._load_deprecated_configuration()
            return

        with open(resource_map_file, 'r') as f:
            data = yaml.load(f)
            if data is None:
                cls._load_deprecated_configuration()
            else:
                if not isinstance(data, dict):
                    raise TypeError('%s root object must be dictionary!' %
                                    (resource_map_file,))
                cls._config = data

    @classmethod
    def _load_deprecated_configuration(cls):
        ext_net_map_file = CONF.migrate.ext_net_map
        if not os.path.exists(ext_net_map_file):
            LOG.warning('Mapping configuration is absent!')
            cls._config = {}
            return

        with open(ext_net_map_file, 'r') as f:
            data = yaml.load(f)
            if data is None:
                cls._config = {}
            else:
                if not isinstance(data, dict):
                    raise TypeError('%s root object must be dictionary!' %
                                    (ext_net_map_file,))
                cls._config = {'ext_network_map': data}

    def __init__(self, mapping_name):
        if self._config is None:
            self._load_configuration()
        self._mapping = self._config.get(mapping_name, {})

    def __getitem__(self, item):
        return self._mapping[item]

    def __contains__(self, item):
        return item in self._mapping

    def get(self, item, default=None):
        return self._mapping.get(item, default)

    def map(self, value):
        return self._mapping.get(value, value)

    def iteritems(self):
        return self._mapping.iteritems()
