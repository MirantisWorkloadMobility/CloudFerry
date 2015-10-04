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


import copy

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class ConvertComputeToVolume(action.Action):

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        storage_info = {utl.VOLUMES_TYPE: {}}
        ignored = {}
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            volumes_exists = True
            if not instance[utl.INSTANCE_BODY]['volumes']:
                if 'volume' in instance['meta']:
                    if not instance['meta']['volume']:
                        volumes_exists = False
                else:
                    volumes_exists = False
            if not volumes_exists:
                ignored[instance_id] = instance
            for v in instance[utl.INSTANCE_BODY]['volumes']:
                volume = resource_storage.read_info(id=v['id'])
                volume[utl.VOLUMES_TYPE][v['id']][
                    'num_device'] = v['num_device']
                volume[utl.VOLUMES_TYPE][v['id']][
                    utl.META_INFO]['instance'] = instance
                storage_info[utl.VOLUMES_TYPE].update(
                    volume[utl.VOLUMES_TYPE])

            if 'volume' in instance['meta']:
                for v in instance['meta']['volume'].itervalues():
                    v = v[utl.VOLUME_BODY]
                    storage_info[utl.VOLUMES_TYPE][v['id']] = {
                        utl.META_INFO: {}, utl.VOLUME_BODY: {}}
                    storage_info[utl.VOLUMES_TYPE][v['id']][
                        utl.META_INFO]['instance'] = instance
                    storage_info[utl.VOLUMES_TYPE][v['id']][
                        utl.VOLUME_BODY] = v
        return {
            'storage_info': storage_info,
            'compute_ignored': ignored
        }
