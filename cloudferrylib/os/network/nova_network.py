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


from fabric.api import env
from fabric.api import run
from fabric.api import settings

from novaclient.v1_1 import client as nova_client

from cloudferrylib.base import network
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.utils.utils import forward_agent


class NovaNetwork(network.Network):
    def __init__(self, config, cloud):
        super(NovaNetwork, self).__init__(config)
        self.cloud = cloud

    @property
    def nova_client(self):
        return self.proxy(self.get_client(), self.config)

    def get_client(self):
        return nova_client.Client(
            self.config.cloud.user,
            self.config.cloud.password,
            self.config.cloud.tenant,
            self.config.cloud.auth_url)

    def read_info(self, opts=None):
        opts = {} if not opts else opts
        instance = opts['instance']
        resource = {'security_groups': self.get_security_groups(instance)}
        return resource

    def deploy(self, info):
        self.upload_security_groups(info['security_groups'])

    def get_security_groups(self, instance=None):
        if instance is None:
            return self.convert_to_dict_sc_grs(
                self.nova_client.security_groups.list())
        return self.convert_to_dict_sc_grs(
            self.nova_client.security_groups.list(instance))

    @staticmethod
    def convert_to_dict_sc_grs(sc_grs):
        # TODO: Refactor this code. Mapping params to dict.
        return [x.__dict__ for x in sc_grs]

    def upload_security_groups(self, security_groups):
        existing = {sg.name for sg in self.get_security_groups()}
        for security_group in security_groups:
            if security_group.name not in existing:
                sg = self.nova_client.security_groups.create(
                    name=security_group.name,
                    description=security_group.description)
                for rule in security_group.rules:
                    self.nova_client.security_group_rules.create(
                        parent_group_id=sg.id,
                        ip_protocol=rule['ip_protocol'],
                        from_port=rule['from_port'],
                        to_port=rule['to_port'],
                        cidr=rule['ip_range']['cidr'])

    def get_func_mac_address(self, instance):
        list_mac = self.get_mac_addresses(instance)
        return lambda x: next(list_mac)

    def get_mac_addresses(self, instance):
        compute_node = getattr(instance, nova_compute.INSTANCE_HOST_ATTRIBUTE)
        libvirt_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')

        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                cmd = "virsh dumpxml %s | grep 'mac address' | " \
                      "cut -d\\' -f2" % libvirt_name
                out = run("ssh -oStrictHostKeyChecking=no %s %s" %
                          (compute_node, cmd))
                mac_addresses = out.split()
        mac_iter = iter(mac_addresses)
        return mac_iter
