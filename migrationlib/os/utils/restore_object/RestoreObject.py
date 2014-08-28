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


def ImageTransferRestore(obj, inst_exporter=None, **kwargs):
    glance_client = inst_exporter.glance_client
    return ImageTransfer(obj['image_id'], glance_client)


def VolumeTransferRestore(obj, inst_exporter=None, **kwargs):
    glance_client = inst_exporter.glance_client
    return VolumeTransfer(None, None, None, glance_client, obj)


def ImageGlanceClientV1Restore(obj, inst_importer=None, **kwargs):
    return inst_importer.glance_client.images.get(obj['id'])


def InstanceNovaClientV1Restore(obj, inst_importer=None, **kwargs):
    return inst_importer.nova_client.servers.get(obj['id'])


def FlavorNovaClientV1Restore(obj, inst_importer=None, **kwargs):
    return inst_importer.nova_client.flavors.find(name=obj['name'])


class RestoreObject:
    def __init__(self):
        self.classes = {
            'ImageTransfer': ImageTransferRestore,
            'VolumeTransfer': VolumeTransferRestore,
            "<class 'glanceclient.v1.images.Image'>": ImageGlanceClientV1Restore,
            "<class 'novaclient.v1_1.servers.Instance'>": InstanceNovaClientV1Restore,
            "<class 'novaclient.v1_1.flavors.Flavor'>": FlavorNovaClientV1Restore
        }

    def restore(self, obj, namespace):
        if not '_type_class' in obj:
            return obj
        type_class = self.own_type_class(obj['_type_class'])
        if type_class == DEFAULT:
            return obj
        return type_class(obj, **namespace.vars)

    def own_type_class(self, type_class):
        if type_class in self.classes:
            return self.classes[type_class]
        return DEFAULT