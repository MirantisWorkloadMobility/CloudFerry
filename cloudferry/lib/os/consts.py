# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class EnumType(object):
    @classmethod
    def _is_field(cls, name):
        if name.startswith('_'):
            return False
        field = getattr(cls, name)
        return not hasattr(field, '__call__')

    @classmethod
    def names(cls):
        return [f for f in dir(cls) if cls._is_field(f)]

    @classmethod
    def values(cls):
        return [getattr(cls, f) for f in cls.names()]

    @classmethod
    def items(cls):
        return [(f, getattr(cls, f)) for f in cls.names()]


class ServiceType(EnumType):
    IDENTITY = 'identity'
    COMPUTE = 'compute'
    NETWORK = 'network'
    IMAGE = 'image'
    VOLUME = 'volume'
