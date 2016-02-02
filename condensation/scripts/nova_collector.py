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
from cloudferrylib.utils import log
from cloudferrylib.os.compute import nova_compute
from condensation import utils as condensation_utils


LOG = log.getLogger(__name__)


def get_flavors_vms_and_nodes(conf):
    """Returns information about flavors and VMs in the source cloud.

    Return format:
    ({
        <VM ID>: {
            "id": <VM ID>,
            "flavor": <VM flavor>,
            "host": <host VM is running on>,
        }
    },
    {
        <flavor ID>: {
            "fl_id": <flavor ID>,
            "core": <number of cores for flavor>,
            "name": <flavor name>,
            "ram": <amount of RAM required for flavor>,
            "ephemeral": <amount of ephemeral storage required for flavor>,
            "swap": <swap space needed for flavor>
        }
    },
    {
        <hostname>: {
            'core': <number of cores/CPUs>,
            'ram': <amount of RAM>,
            'core_ratio': <CPU allocation ratio>,
            'ram_ratio': <RAM allocation ratio>,
        }
    })"""
    src = conf['src']
    username = src['user']
    password = src['password']
    tenant = src['tenant']
    auth_url = src['auth_url']
    region = src.get('region')

    dst_comp = conf['dst_compute']
    core_ratio = dst_comp['cpu_allocation_ratio']
    ram_ratio = dst_comp['ram_allocation_ratio']

    cli = client.Client(2, username, password, tenant, auth_url,
                        region_name=region)
    servers = cli.servers.list(search_opts={"all_tenants": True})
    nova_flavors = cli.flavors.list()

    flavors = {
        i.id: {
            "fl_id": i.id,
            "core": i.vcpus,
            "name": i.name,
            "ram": i.ram,
            "ephemeral": i.ephemeral,
            "swap": i.swap
        } for i in nova_flavors
    }

    hypervisors = {}

    down_hosts = set([service.host for service in cli.services.findall(
        binary='nova-compute', state='down')])

    def vm_host_is_up(vm):
        host_is_up = (getattr(vm, nova_compute.INSTANCE_HOST_ATTRIBUTE)
                      not in down_hosts)
        if not host_is_up:
            LOG.warning("VM '%s' is running on a down host! Skipping.", vm.id)

        return host_is_up

    def vm_is_in_valid_state(vm):
        return vm.status in nova_compute.ALLOWED_VM_STATUSES

    vms = {
        vm.id: {
            "id": vm.id,
            "flavor": vm.flavor.get("id"),
            "host": getattr(vm,
                            nova_compute.INSTANCE_HOST_ATTRIBUTE)
        } for vm in servers if vm_host_is_up(vm) and vm_is_in_valid_state(vm)
    }

    for hypervisor in cli.hypervisors.list():
        host = hypervisor.hypervisor_hostname
        if host not in down_hosts:
            hypervisors[host] = {
                'core': hypervisor.vcpus,
                'ram': hypervisor.memory_mb,
                'core_ratio': core_ratio,
                'ram_ratio': ram_ratio}

    return flavors, vms, hypervisors


def run_it(conf):
    """
    This function is entry point of this Program.
    The Program read information on source cloud:
     - about flavors and instances and store it into 'configs/nova.json'
     - about compute nodes and store it into 'configs/nodes_info.json'
    """
    flavors, vms, nodes = get_flavors_vms_and_nodes(conf)
    condensation_utils.store_condense_data(flavors, nodes, vms)
