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

__author__ = 'mirrorcoder'


class StateCloud(object):
    def __init__(self, cloud, list_subclass=[]):
        self.cloud = cloud
        self.keystone_client = cloud.keystone_client
        self.nova_client = cloud.nova_client
        self.cinder_client = cloud.cinder_client
        self.network_client = cloud.network_client
        self.glance_client = cloud.glance_client
        self.keystone_db_conn_url = cloud.keystone_client
        self.config_snapshots = [inst(cloud) for inst in list_subclass]