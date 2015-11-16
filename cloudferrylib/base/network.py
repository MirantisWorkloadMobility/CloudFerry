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

from cloudferrylib.base import resource


class Network(resource.Resource):

    def __init__(self, config):
        self.config = config
        super(Network, self).__init__()

    def get_func_mac_address(self, instance):
        raise NotImplemented("it's base class")

    def create_port(self, net_id, mac, ip, tenant_id, keep_ip, sg_ids=None):
        raise NotImplemented("it's base class")

    def delete_port(self, port_id):
        raise NotImplemented("it's base class")

    def check_existing_port(self, network_id, mac, ip_address):
        raise NotImplemented("it's base class")

    def get_security_groups(self):
        raise NotImplemented("it's base class")
