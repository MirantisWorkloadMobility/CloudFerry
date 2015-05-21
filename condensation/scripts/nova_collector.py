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


username = ""
password = ""
tenant = ""
auth_url = ""

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

with open("nova.json", "w") as descriptor:
    json.dump(result, descriptor)
