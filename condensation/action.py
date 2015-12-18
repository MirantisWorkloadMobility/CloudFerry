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

import unicodedata
import data_storage
import json

from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


TRANSFER = "transfer"
MIGRATE = "migrate"
CONDENSE = "condense"


def normalize(string):
    """
        This function encodes unicode to string
    """
    return unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')


def get_key(iteration, name):
    # iteration - number of iteration
    # name - cloud name
    return "_".join([str(iteration), name])


class Actions(object):

    """
        This class stores all messages of particular cloud
        and dumps all messages to different files
    """

    def __init__(self, name):
        self.iteration = 0
        # name of the cloud that performs actions
        self.name = name
        self.new_step()

    def new_step(self):
        """
            This method responds is called at the begining of new step
            we need to refresh our state to initial
        """
        self.data = {
            TRANSFER: [],
            MIGRATE: [],
            CONDENSE: []
        }

    @property
    def key(self):
        """
            unique key to store data in key-value database
        """
        return get_key(self.iteration, self.name)

    def dump_actions(self):
        """
            This method writes all actions on the current step to database
        """
        data_storage.put(self.key, json.dumps(self.data))
        self.new_step()
        self.iteration += 1

    def add_migration_action(self, vm_obj, target_node):
        """
            This method adds entry to MIGRATE chain
        """
        LOG.debug("migrate vm %s to node %s" % (
            vm_obj.vm_id, target_node.name))
        payload = map(normalize, [vm_obj.vm_id, target_node.name])
        self.data[MIGRATE].append(payload)

    def add_transfer_action(self, node_name):
        """
            This method adds entry to TRANSFER chain
        """
        LOG.debug("transfer_node " + node_name)
        payload = normalize(node_name)
        self.data[TRANSFER].append(payload)

    def add_condensation_action(self, vm_obj, source_node, target_node):
        """
            This method adds entry to CONDENSE chain
        """
        LOG.debug("condense vm %s from node %s to node %s" % (vm_obj.vm_id,
                                                              source_node.name,
                                                              target_node.name)
                  )
        payload = map(normalize, [vm_obj.vm_id, target_node.name])
        self.data[CONDENSE].append(payload)


def get_freed_nodes(iteration):
    try:
        condense_data = json.loads(
            data_storage.get(get_key(iteration, 'source')))
        return condense_data.get(TRANSFER, [])
    except (TypeError, ValueError):
        LOG.error("Something went wrong while retrieving freed nodes from DB, "
                  "check iteration value passed")
