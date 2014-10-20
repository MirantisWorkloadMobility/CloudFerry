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

from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl
__author__ = 'mirrorcoder'


class CreateNewVolumes(action.Action):

    def __init__(self, cloud):
        self.cloud = cloud
        super(CreateNewVolumes, self).__init__()

    def run(self, volumes=None, **kwargs):
        storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        volumes_new = storage.deploy(volumes)
        return {
            'volumes_new': volumes_new
        }
