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

import os
import re
import json
import subprocess


def process_execution(command):
    process = subprocess.Popen(command, shell=True, cwd=os.getcwd(),
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    output, error = process.communicate()
    returncode = process.returncode
    if returncode:
        pass
    else:
        return output


output = process_execution(['knife search node "roles:*compute*" -F json'])
output_dict = json.loads(output)
results = output_dict.get('rows')
result_dict = {}
for i in results:
    name = i['name']
    core = i['automatic']['cpu']['total']
    memory = re.findall('\d+', i['automatic']['memory']['total'])
    if memory:
        # convert memory from kilobytes to megabytes
        memory = int(memory[0]) / 1024
    core_ratio = i['default']['openstack'][
        'compute']['config']['cpu_allocation_ratio']
    ram_ratio = i['default']['openstack'][
        'compute']['config']['ram_allocation_ratio']
    result_dict.update(
        {name: {
            'core': core,
            'ram': memory,
            'core_ratio': core_ratio,
            'ram_ratio': ram_ratio}})

with open('nodes_info.json', 'w') as nodes_descriptor:
    json.dump(result_dict, nodes_descriptor)
