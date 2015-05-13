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

from novaclient import client
import json
from cloudferrylib.os.compute import nova_compute


def run_it(conf):
    """
    This function is entry point of this Program.
    The Program read information on source cloud:
     - about flavors and instances and store it into 'configs/nova.json'
     - about compute nodes and store it into 'configs/nodes_info.json'
    """
    src = conf['src']
    username = src['user']
    password = src['password']
    tenant = src['tenant']
    auth_url = src['auth_url']
    dst_comp = conf['dst_compute']
    core_ratio = dst_comp['cpu_allocation_ratio']
    ram_ratio = dst_comp['ram_allocation_ratio']

    cli = client.Client(2, username, password, tenant, auth_url)
    servers = cli.servers.list(search_opts={"all_tenants": True})
    flavors = cli.flavors.list()
    result = {"vms": {i.id:
                      {"id": i.id,
                       "flavor": i.flavor.get("id"),
                       "host": getattr(i, nova_compute.INSTANCE_HOST_ATTRIBUTE)
                       } for i in servers
                      },
              "flavors": {i.id:
                          {"fl_id": i.id,
                              "core": i.vcpus,
                              "name": i.name,
                              "ram": i.ram,
                              "ephemeral": i.ephemeral,
                              "swap": i.swap
                           } for i in flavors}}

    with open("configs/nova.json", "w") as descriptor:
        json.dump(result, descriptor)

    result_dict = {}

    down_hosts = set([service.host for service in cli.services.findall(
        binary='nova-compute', state='down')])

    for hypervisor in cli.hypervisors.list():
        host = hypervisor.hypervisor_hostname
        if host not in down_hosts:
            result_dict[host] = {
                    'core': hypervisor.vcpus,
                    'ram': hypervisor.memory_mb,
                    'core_ratio': core_ratio,
                    'ram_ratio': ram_ratio}

    with open('configs/nodes_info.json', 'w') as nodes_descriptor:
        json.dump(result_dict, nodes_descriptor)
