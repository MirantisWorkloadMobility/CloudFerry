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

import time
from cloudferrylib.base.Compute import Compute
__author__ = 'toha'


class NovaCompute(Compute):

    """
    The main class for working with Openstack Nova Compute Service.

    """

    def __init__(self, nova_client, data_for_instance=None, instance=None):
        self.nova_client = nova_client
        self.data_for_instance = data_for_instance if data_for_instance \
            else dict()
        self.instance = instance if instance else object()
        super(NovaCompute, self).__init__()

    def create_instance(self, data_for_instance=None, **kwargs):
        data_for_instance = data_for_instance if data_for_instance \
            else self.data_for_instance
        self.instance = self.nova_client.servers.create(**data_for_instance)
        return self.instance.id

    def change_status(self, status, instance=None, **kwargs):
        instance = instance if instance else self.instance
        status_map = {
            'start': lambda instance: instance.start(),
            'stop': lambda instance: instance.stop(),
            'resume': lambda instance: instance.resume(),
            'paused': lambda instance: instance.pause(),
            'unpaused': lambda instance: instance.unpause(),
            'suspend': lambda instance: instance.suspend()}
        if self.get_status(self.nova_client.servers, instance.id).lower() \
                != status:
            status_map[status](instance)

    def get_instance_info_by_id(self, id):
        pass

    def wait_for_status(self, getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)

    def get_status(self, getter, id):
        return getter.get(id).status
