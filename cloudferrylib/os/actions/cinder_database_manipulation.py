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


import abc
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils
import jsondate

NAMESPACE_CINDER_CONST = "cinder_database"


class CinderDatabaseInteraction(action.Action):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def run(self, *args, **kwargs):
        pass

    def get_resource(self):
        cinder_resource = self.cloud.resources.get(
            utils.STORAGE_RESOURCE)
        if not cinder_resource:
            raise RuntimeError(
                "No resource {res} found".format(res=utils.STORAGE_RESOURCE))
        return cinder_resource


class GetVolumesDb(CinderDatabaseInteraction):

    def run(self, *args, **kwargs):
        search_opts = kwargs.get('search_opts_tenant', {})
        return {NAMESPACE_CINDER_CONST: \
            self.get_resource().read_db_info(**search_opts)}


class WriteVolumesDb(CinderDatabaseInteraction):

    def run(self, *args, **kwargs):
        data_from_namespace = kwargs.get(NAMESPACE_CINDER_CONST)
        if not data_from_namespace:
            raise RuntimeError(
                "Cannot read attribute {attribute} from namespace".format(
                    attribute=NAMESPACE_CINDER_CONST))
        data = jsondate.loads(data_from_namespace)
        # mark attached volumes as available
        for volume in data['volumes']:
            if volume['status'] == 'in-use':
                volume['mountpoint'] = None
                volume['status'] = 'available'
                volume['instance_uuid'] = None
                volume['attach_status'] = 'detached'
        self.get_resource().deploy(jsondate.dumps(data))
