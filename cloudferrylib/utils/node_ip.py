# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import socket
from fabric.context_managers import settings
from fabric.operations import run
from fabric.state import env
import ipaddr

from cloudferrylib.utils import log


LOG = log.getLogger(__name__)


def get_ext_ip(ext_cidr, init_host, compute_host, ssh_user):
    list_ips = get_ips(init_host, compute_host, ssh_user)
    for ip_str in list_ips:
        ip_addr = ipaddr.IPAddress(ip_str)
        for cidr in ext_cidr:
            if ipaddr.IPNetwork(cidr.strip()).Contains(ip_addr):
                return ip_str
    LOG.warning("Unable to find IP address of '%s' node, please "
                "check ext_cidr config value.", compute_host)
    return socket.gethostbyname(compute_host)


def get_ips(init_host, compute_host, ssh_user):
    with settings(host_string=compute_host,
                  user=ssh_user,
                  gateway=init_host,
                  connection_attempts=env.connection_attempts):
        cmd = ("ifconfig | awk -F \"[: ]+\" \'/inet addr:/ "
               "{ if ($4 != \"127.0.0.1\") print $4 }\'")
        out = run(cmd)
        list_ips = []
        for info in out.split():
            try:
                ipaddr.IPAddress(info)
            except ValueError:
                continue
            list_ips.append(info)
    return list_ips
