# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import re

from cloudferry import discover
from cloudferry import model
from cloudferry.model import compute
from cloudferry.lib.utils import remote

LOG = logging.getLogger(__name__)
IFACE_RE = re.compile(r'^\d+: ([^:]+):.*$')
ADDR_RE = re.compile(r'^inet (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}/\d{1,2}) .*$')


class ComputeNodeDiscoverer(discover.Discoverer):
    discovered_class = compute.ComputeNode

    def discover_all(self):
        # TODO: implement
        return

    def discover_one(self, uuid):
        hostname = uuid

        with remote.RemoteExecutor(self.cloud, hostname) as remote_executor:
            try:
                ip_addr_output = remote_executor.sudo('ip addr show')
                interfaces = _parse_interfaces(ip_addr_output)
            except remote.RemoteFailure:
                LOG.warn('Unable to get network interfaces of node: %s',
                         hostname)
                LOG.debug('Unable to get network interfaces of node: %s',
                          hostname, exc_info=True)
                interfaces = {}

        # Store server
        with model.Session() as session:
            compute_node = self.load_from_cloud({
                'hostname': hostname,
                'interfaces': interfaces,
            })
            session.store(compute_node)
        return compute_node

    def load_from_cloud(self, data):
        compute_node_dict = {
            'object_id': self.make_id(data['hostname']),
            'interfaces': data['interfaces'],
        }
        return compute.ComputeNode.load(compute_node_dict)


def _parse_interfaces(ip_addr_output):
    result = {}
    iface = None
    for line in ip_addr_output.strip().splitlines():
        iface_m = IFACE_RE.match(line)
        if iface_m:
            iface = iface_m.group(1)
            continue
        if not iface:
            continue
        addr_m = ADDR_RE.match(line.strip())
        if addr_m:
            result.setdefault(iface, []).append(addr_m.group(1))
    return result
