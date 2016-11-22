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
from cloudferry.lib.migration import objects


class MigrationStateNotifier(object):
    def __init__(self):
        self.observers = []

    def add_observer(self, observer):
        self.observers.append(observer)

    def success(self, object_type, src_object, dst_object_id, message=None):
        self._update_state(object_type, src_object,
                           objects.MigrationState.SUCCESS,
                           message)
        for observer in self.observers:
            observer.set_dst_uuid(object_type, src_object, dst_object_id)

    def fail(self, object_type, obj, message=None):
        self._update_state(object_type, obj,
                           objects.MigrationState.FAILURE, message)

    def incomplete(self, object_type, obj, message=None):
        self._update_state(object_type, obj,
                           objects.MigrationState.INCOMPLETE,
                           message)

    def skip(self, object_type, obj, message=None):
        self._update_state(object_type, obj,
                           objects.MigrationState.SKIPPED, message)

    def _update_state(self, object_type, obj, new_state, message):
        for observer in self.observers:
            observer.update_state(object_type, obj, new_state)
            observer.set_message(object_type, obj, message)

    def append_message(self, object_type, obj, message):
        for observer in self.observers:
            observer.append_message(object_type, obj, message)
