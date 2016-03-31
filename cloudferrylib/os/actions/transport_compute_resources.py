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
import copy

from cloudferrylib.base.action import action
from cloudferrylib.os.compute import keypairs
from cloudferrylib.os.identity import keystone
from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)


class TransportComputeResources(action.Action):
    def run(self, info=None, **kwargs):
        info = copy.deepcopy(info)
        target = 'resources'
        search_opts = {'target': target}
        search_opts.update(kwargs.get('search_opts_tenant', {}))

        src_compute = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        dst_compute = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]

        info_res = src_compute.read_info(**search_opts)

        tenant_map = self.get_similar_tenants()
        user_map = self.get_similar_users()

        new_info = dst_compute.deploy(info_res, target=target,
                                      tenant_map=tenant_map, user_map=user_map)

        if info:
            new_info[utl.INSTANCES_TYPE] = info[utl.INSTANCES_TYPE]

        return {
            'info': new_info
        }


class TransportKeyPairs(action.Action):
    """
    # Overview

    Key pair migration is special because
      - key pair is associated with user's ID;
      - user's key pair is not accessible by admin.
    Because of that there should be a low-level SQL call implemented to migrate
    key pairs.

    # DB model

     - `nova.key_pairs` table (identical for grizzly and icehouse):
    +-------------+--------------+------+-----+---------+----------------+
    | Field       | Type         | Null | Key | Default | Extra          |
    +-------------+--------------+------+-----+---------+----------------+
    | created_at  | datetime     | YES  |     | NULL    |                |
    | updated_at  | datetime     | YES  |     | NULL    |                |
    | deleted_at  | datetime     | YES  |     | NULL    |                |
    | id          | int(11)      | NO   | PRI | NULL    | auto_increment |
    | name        | varchar(255) | YES  |     | NULL    |                |
    | user_id     | varchar(255) | YES  | MUL | NULL    |                |
    | fingerprint | varchar(255) | YES  |     | NULL    |                |
    | public_key  | mediumtext   | YES  |     | NULL    |                |
    | deleted     | int(11)      | YES  |     | NULL    |                |
    +-------------+--------------+------+-----+---------+----------------+

    # Migration process notes

     - It is assumed that user names in keystone are unique
     - It is assumed that users are migrated to DST
     - Since keystone backend can be LDAP as well, user names and IDs must be
       fetched through keystone API, not the low-level SQL
     - Update DST DB with key pairs from SRC using SQL
    """

    def __init__(self, init, kp_db_broker=keypairs.DBBroker, **kwargs):
        super(TransportKeyPairs, self).__init__(init)
        self.kp_db_broker = kp_db_broker

    def run(self, **kwargs):
        """Since user IDs on SRC and DST may be different, we must update the
        DST ids for key pairs with IDs from DST (see `nova.key_pairs` table
        schema)"""
        src_keystone = self.src_cloud.resources[utl.IDENTITY_RESOURCE]
        dst_keystone = self.dst_cloud.resources[utl.IDENTITY_RESOURCE]

        dst_users = {}
        key_pairs = self.kp_db_broker.get_all_keypairs(self.src_cloud)

        # If we want to skip orphaned key pairs - we should not switch
        # to the admin if dst_user doesn't exist
        fallback_to_admin = not self.cfg.migrate.skip_orphaned_keypairs

        for key_pair in key_pairs:
            if key_pair.user_id not in dst_users:
                dst_user = keystone.get_dst_user_from_src_user_id(
                    src_keystone, dst_keystone, key_pair.user_id,
                    fallback_to_admin=fallback_to_admin)
                dst_users[key_pair.user_id] = dst_user
            else:
                dst_user = dst_users[key_pair.user_id]
            if dst_user is None:
                continue

            key_pair.user_id = dst_user.id

            LOG.debug('Adding key pair %s for user %s on DST', key_pair.name,
                      dst_user.name)
            self.kp_db_broker.store_keypair(key_pair, self.dst_cloud)


class SetKeyPairsForInstances(action.Action):
    """
    Keypair migration process requires key pair to be associated with a VM on
    a lower DB level.
    """
    def __init__(self, init, kp_db_broker=keypairs.DBBroker, **kwargs):
        super(SetKeyPairsForInstances, self).__init__(init)
        self.kp_db_broker = kp_db_broker

    def run(self, info=None, **kwargs):
        if info is None:
            LOG.warning("Task '%s' is called without required arguments being "
                        "passed. Nothing will be done. Check your migration "
                        "scenario.", self.__class__.__name__)
            return

        instances = info[utl.INSTANCES_TYPE]
        for instance_id in instances:
            instance = instances[instance_id][utl.INSTANCE_BODY]
            key_name = instance.get('key_name')
            user_id = instance.get('user_id')

            if key_name is not None and user_id is not None:
                LOG.info("Associating key pair '%s' with instance '%s'",
                         key_name, instance_id)
                self.kp_db_broker.add_keypair_to_instance(
                    self.dst_cloud, key_name, user_id, instance_id)
