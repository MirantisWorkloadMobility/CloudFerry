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

    def __init__(self, config, cloud):
        self.config = config
        self.cloud = cloud
        super(ConvertComputeToVolume, self).__init__()

    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        info[utl.STORAGE_RESOURCE] = {utl.VOLUMES_TYPE: {}}
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        for instance in info[utl.COMPUTE_RESOURCE][
                utl.INSTANCES_TYPE].itervalues():
            for v in instance[utl.INSTANCE_BODY]['volumes']:
                volume = resource_storage.read_info(id=v['id'])
                volume[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']][
                    'num_device'] = v['num_device']
                volume[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']][
                    utl.META_INFO]['instance'] = instance
                info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE].update(
                    volume[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE])

            if 'volume' in instance['meta']:
                for v in instance['meta']['volume']:
                    v = v[utl.VOLUME_BODY]
                    info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']] = {
                        utl.META_INFO: {}, utl.VOLUME_BODY: {}}
                    info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']][
                        utl.META_INFO]['instance'] = instance
                    info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']][
                        utl.VOLUME_BODY] = v

        info.pop('compute')
        return {
            'storage_info': info
        }
