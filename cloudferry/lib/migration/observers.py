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
import abc
import logging
import os

from cloudferry.lib.migration import objects
from cloudferry.lib.migration.objects import get_obj_id

LOG = logging.getLogger(__name__)


class MigrationObserver(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def set_dst_uuid(self, object_type, src_uuid, dst_uuid):
        pass

    @abc.abstractmethod
    def update_state(self, object_type, uuid, new_state):
        pass

    @abc.abstractmethod
    def set_message(self, object_type, uuid, message):
        pass

    @abc.abstractmethod
    def append_message(self, object_type, uuid, message):
        pass


class MemoizingMigrationObserver(MigrationObserver):
    def __init__(self):
        super(MemoizingMigrationObserver, self).__init__()
        self.storage = {}

    def _add_new_object(self, object_type, obj, dst_uuid=None, message=None):
        uuid = objects.get_obj_id(obj)
        ot = self.storage.setdefault(object_type, {})
        o = objects.MigrationObject(object_type=object_type,
                                    obj=obj,
                                    dst_uuid=dst_uuid,
                                    state=objects.MigrationState.UNKNOWN,
                                    message=message)
        ot[uuid] = o
        return self.get_object(object_type, obj)

    def _get_or_create(self, object_type, obj, dst_uuid=None, message=None):
        internal_obj = self.get_object(object_type, obj)
        if internal_obj is None:
            return self._add_new_object(object_type, obj, dst_uuid, message)
        return internal_obj

    def set_message(self, object_type, obj, message):
        obj = self._get_or_create(object_type, obj)
        obj.message = message

    def append_message(self, object_type, obj, message):
        obj = self._get_or_create(object_type, obj)
        obj.message += (os.linesep + message)

    def set_dst_uuid(self, object_type, src_obj, dst_obj):
        obj = self._get_or_create(object_type, src_obj)
        obj.dst_uuid = dst_obj

    def update_state(self, object_type, obj, new_state):
        obj = self._get_or_create(object_type, obj)
        obj.state = new_state

    def get_object(self, object_type, obj):
        try:
            uuid = get_obj_id(obj)
            if uuid is None:
                LOG.debug("Can't store information about %s '%s': "
                          "object has no UUID (should not happen)",
                          object_type, obj)
            else:
                return self.storage[object_type][uuid]
        except (KeyError, TypeError):
            return None


class LoggingMigrationObserver(MigrationObserver):
    def set_dst_uuid(self, object_type, src_object, dst_uuid):
        LOG.debug("%(obj_type)s ID=%(src_object)s has ID=%(dst_uuid)s in "
                  "destination", {"obj_type": object_type,
                                  "src_object": src_object,
                                  "dst_uuid": dst_uuid})

    def append_message(self, object_type, uuid, message):
        self._log_message(message, object_type, uuid)

    @staticmethod
    def _log_message(message, object_type, obj):
        LOG.debug("%(obj_type)s %(object)s: %(message)s",
                  {"obj_type": object_type, "object": obj, "message": message})

    def update_state(self, object_type, obj, new_state):
        LOG.debug("%(obj_type)s with ID=%(object)s changed state to %(state)s",
                  {"obj_type": object_type, "object": obj, "state": new_state})

    def set_message(self, object_type, uuid, message):
        self._log_message(message, object_type, uuid)


class MigrationObserverReporter(object):
    def __init__(self, observer):
        self.observer = observer

    def report(self):
        if not hasattr(self.observer, 'storage'):
            return

        columns = ('#',
                   'Object Type',
                   'Source object',
                   'Destination ID',
                   'Status',
                   'Info')
        data = []
        for i, object_type in enumerate(self.observer.storage, start=1):
            migrated_objs = self.observer.storage[object_type].values()
            for j, obj in enumerate(migrated_objs, start=1):
                index = ".".join([str(i), str(j)])
                d = (index, obj.object_type, obj.name(),
                     obj.dst_uuid, obj.state, obj.message)
                data.append(d)

        return columns, data
