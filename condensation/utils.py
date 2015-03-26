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

import json
from cfglib import CONF
import yaml


def read_file(path):
    """This function reads yaml / json files"""

    # check if path has extension
    if '.' not in path:
        raise RuntimeError("File {path} has no extension".format(path=path))
    extension = path.split(".")[-1]

    # check if extension is json or yml
    extension_map = {"json": json, "yml": yaml}
    if extension not in extension_map:
        raise RuntimeError(
            "File extension of {path} is not yaml/json".format(path=path))

    # do actual job
    with open(path) as descriptor:
        return extension_map.get(extension).load(descriptor)


def read_initial_state():
    nova = read_file(CONF.condense.nova_file)
    flavors = nova.get("flavors")
    vms = nova.get("vms")
    return (read_file(CONF.condense.node_file),
            flavors, vms,
            read_file(CONF.condense.group_file))
