# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cloudferry.lib.os import consts


def _try_get_item(obj, attrs):
    if hasattr(obj, 'get'):
        for attr in attrs:
            try:
                return obj[attr]
            except KeyError:
                pass
            except TypeError:
                return None


def _try_get_attr(obj, attrs):
    for attr in attrs:
        if hasattr(obj, attr):
            return getattr(obj, attr)


def _try_get(obj, attrs):
    name = _try_get_attr(obj, attrs)
    if name is None:
        name = _try_get_item(obj, attrs)
    return name


def get_obj_name(obj):
    return _try_get(obj, ['name', 'display_name', 'floating_ip_address'])


def get_obj_id(obj):
    return _try_get(obj, ['id'])


def human_readable_name(obj):
    name = get_obj_name(obj) or "<NO NAME>"
    uuid = get_obj_id(obj) or "<NO ID>"
    return "{name} ({uuid})".format(name=name, uuid=uuid)


class MigrationState(consts.EnumType):
    SUCCESS = 'success'
    FAILURE = 'fail'
    SKIPPED = 'skipped'
    INCOMPLETE = 'incomplete'
    UNKNOWN = 'unknown'


class MigrationObjectType(consts.EnumType):
    VOLUME = 'volume'
    VM = 'VM'
    IMAGE = 'image'
    FLOATING_IP = 'floating IP'
    NET = 'network'
    TENANT = 'tenant'
    ROLE = 'user role'


class MigrationObject(object):
    def __init__(self, object_type=None, obj=None, dst_uuid=None,
                 state=MigrationState.UNKNOWN, message=None):
        self.object_type = object_type
        self.obj = obj
        self.uuid = get_obj_id(obj)
        self.dst_uuid = dst_uuid
        self.state = state
        self.message = message if message else ""

    def name(self):
        return human_readable_name(self.obj)

    def __repr__(self):
        return ("{obj_type}<src_id={uuid},dst_id={dst_uuid},state={state},"
                "msg={msg}").format(obj_type=self.object_type, uuid=self.uuid,
                                    dst_uuid=self.dst_uuid, state=self.state,
                                    msg=self.message)

    def __hash__(self):
        return self.object_type + self.uuid

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.object_type == other.object_type and
                self.uuid == other.uuid)
