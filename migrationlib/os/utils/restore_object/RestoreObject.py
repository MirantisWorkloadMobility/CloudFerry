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
from migrationlib.os.utils.osImageTransfer import ImageTransfer
from migrationlib.os.utils.osVolumeTransfer import VolumeTransfer
__author__ = 'mirrorcoder'

DEFAULT = 0


class RestoreObject:
    def __init__(self):
        self.classes = {
            'ImageTransfer': ImageTransfer,
            'VolumeTransfer': VolumeTransfer
        }

    def restore(self, obj):
        if not '_type_class' in obj:
            return obj
        type_class = self.own_type_class(obj['_type_class'])
        if type_class == DEFAULT:
            return obj
        return type_class(obj)

    def own_type_class(self, type_class):
        if type_class in self.classes:
            return self.classes[type_class]
        return DEFAULT