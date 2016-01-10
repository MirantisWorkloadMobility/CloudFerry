# Copyright (c) 2015 Mirantis Inc.
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


import data_storage
import json
import yaml
import os

from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


MIGRATE_VM_PREFIX = 'migrate_vm_'


def delete_relations():
    LOG.info("started deleting old VM to hypervisor relations")
    keys = data_storage.keys(MIGRATE_VM_PREFIX + '*')
    data_storage.delete_batch(keys)
    LOG.info("Relation deleting done. %s records was removed." % len(keys))


def check_filter_folder(filter_folder):
    if not os.path.exists(filter_folder):
        os.makedirs(filter_folder)


def make(filter_folder, images_date):
    delete_relations()
    check_filter_folder(filter_folder)
    LOG.info("started creating filter files and all needed resources")
    cursor = 0
    while True:
        step = data_storage.get("%s_source" % cursor)
        if step is None:
            break
        cursor += 1
        ids = []
        for migrate in json.loads(step)['migrate']:
            vm_id = migrate[0]
            ids.append(vm_id)
            data_storage.put(MIGRATE_VM_PREFIX + vm_id, migrate[1])
        vm_filter = {'images': {'date': images_date},
                     'instances': {'id': ids}}
        with file("%s/filter_%s.yaml" % (filter_folder, cursor), 'w') as \
                filter_file:
            filter_file.write(yaml.safe_dump(vm_filter))
    LOG.info("Creating filter files done. %s filters was created." % cursor)
