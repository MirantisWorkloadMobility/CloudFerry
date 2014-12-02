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

from cloudferrylib.base import objstorage
from swiftclient import client as swift_client


class SwiftStorage(objstorage.ObjStorage):
    """The main class for working with Object Storage Service. """

    def __init__(self, config, cloud):
        super(SwiftStorage, self).__init__()
        self.config = config
        self.cloud = cloud
        self.storage_url, self.token = self.get_swift_conn()

    def get_swift_conn(self, params=None):
        """Getting nova client. """
        if params is None:
            params = self.config['cloud']

        conn = swift_client.Connection(user=params['user'],
                                       key=params['password'],
                                       tenant_name=params['tenant'],
                                       authurl="http://%s:35357/v2.0/" % params['host'],
                                       auth_version="2")
        return conn.get_auth()


    def read_info(self, **kwargs):
        info = {'obj_storage':
                    {'containers': {}}}
        account_info = self.get_account_info()
        info['object_storage']['containers'] = account_info[1]
        for container_info in info['object_storage']['containers']:
            container_info['objects'] = self.get_container(container_info['name'])[1]
            for object_info in container_info['objects']:
                resp, object_info['data'] = self.get_object(container_info['name'],
                                                            object_info['name'])
        return info

    def deploy(self, info, **kwargs):
        for container_info in info['object_storage']['containers']:
            self.put_container(container_info['name'])
            for object_info in container_info['objects']:
                self.put_object(container=container_info['name'],
                                obj_name=object_info['name'],
                                content=object_info['data'])

    def get_account_info(self):
        return swift_client.get_account(self.storage_url, self.token)

    def get_container(self, container, *args):
        return swift_client.get_container(self.storage_url, self.token, container, *args)

    def get_object(self, container, obj_name, *args):
        return swift_client.get_object(self.storage_url, self.token, container, obj_name, *args)

    def put_object(self, container, obj_name, content=None, *args):
        return swift_client.put_object(self.storage_url, self.token, container, obj_name, content, *args)

    def put_container(self, container, *args):
        return swift_client.put_container(self.storage_url, self.token, container, *args)

    def delete_container(self, container, *args):
        return swift_client.delete_container(self.storage_url, self.token, container)














