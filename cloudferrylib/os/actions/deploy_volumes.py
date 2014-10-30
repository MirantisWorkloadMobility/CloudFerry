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

class DeployVolumes(action.Action):

    def __init__(self, cloud):
        self.cloud = cloud
        super(DeployVolumes, self).__init__()

    def run(self, volumes_info=None, identity_info=None, **kwargs):
        deploy_info = {utl.STORAGE_RESOURCE: volumes_info[utl.STORAGE_RESOURCE],
                       utl.IDENTITY_RESOURCE: identity_info[utl.IDENTITY_RESOURCE]}
        volume_resource = self.cloud.resources[utl.STORAGE_RESOURCE]
        new_volumes_info = volume_resource.deploy(deploy_info)
        return new_volumes_info



