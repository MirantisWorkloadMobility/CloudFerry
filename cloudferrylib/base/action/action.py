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


from cloudferrylib.scheduler import task
from cloudferrylib.utils import utils


class Action(task.Task):

    def __init__(self, init, cloud=None):
        self.cloud = None
        self.src_cloud = None
        self.dst_cloud = None
        self.cfg = None
        self.__dict__.update(init)
        self.init = init
        if cloud:
            self.cloud = init[cloud]
        super(Action, self).__init__()

    def run(self, **kwargs):
        pass

    def save(self):
        pass

    def restore(self):
        pass

    def get_similar_tenants(self):
        """
        Get SRC tenant ID to DST tenant ID mapping.

        :return dict: {<src_tenant_id>: <dst_tenant_id>, ...}
        """

        src_identity = self.src_cloud.resources[utils.IDENTITY_RESOURCE]
        dst_identity = self.dst_cloud.resources[utils.IDENTITY_RESOURCE]

        src_tenants = src_identity.get_tenants_list()
        dst_tenants = dst_identity.get_tenants_list()

        dst_tenant_map = {tenant.name.lower(): tenant.id for tenant in
                          dst_tenants}

        similar_tenants = {}

        for src_tenant in src_tenants:
            src_tnt_name = src_tenant.name.lower()
            if src_tnt_name in dst_tenant_map:
                similar_tenants[src_tenant.id] = dst_tenant_map[src_tnt_name]

        return similar_tenants

    def get_similar_users(self):
        """
        Get SRC user ID to DST user ID mapping.

        :return dict: {<src_user_id>: <dst_user_id>, ...}
        """

        src_identity = self.src_cloud.resources[utils.IDENTITY_RESOURCE]
        dst_identity = self.dst_cloud.resources[utils.IDENTITY_RESOURCE]

        src_users = src_identity.get_users_list()
        dst_users = dst_identity.get_users_list()

        dst_usr_map = {user.name.lower(): user.id for user in dst_users}

        similar_users = {}

        for src_user in src_users:
            src_user_name = src_user.name.lower()
            if src_user_name in dst_usr_map:
                similar_users[src_user.id] = dst_usr_map[src_user_name]

        return similar_users
