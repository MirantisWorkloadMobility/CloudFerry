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
from operator import attrgetter

from cloudferrylib.base.action import action
from cloudferrylib.base import exception as cf_exceptions
from cloudferrylib.utils import log
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)


class CheckUsersAvailabilityOnSrcAndDst(action.Action):
    """Make sure all users from source cloud are available on destination.
    Migration is aborted if set of users on destination is not a subset of
    users on source.
    """

    def run(self, **kwargs):
        if self.cfg.migrate.migrate_users:
            LOG.info("Users will be migrated. Skipping this check.")
            return
        src_identity = self.src_cloud.resources[utils.IDENTITY_RESOURCE]
        dst_identity = self.dst_cloud.resources[utils.IDENTITY_RESOURCE]

        src_keystone_client = src_identity.get_client()
        dst_keystone_client = dst_identity.get_client()

        LOG.info("Going to get all users from source cloud, this may take a "
                 "while for large LDAP-backed clouds, please be patient")

        src_users = src_keystone_client.users.list()
        dst_users = dst_keystone_client.users.list()

        src_user_names = {name.lower(): name
                          for name in map(attrgetter('name'), src_users)}
        dst_user_names = {name.lower(): name
                          for name in map(attrgetter('name'), dst_users)}

        users_missing_on_dst = \
            set(src_user_names.keys()) - set(dst_user_names.keys())

        if users_missing_on_dst:
            msg = "{n} missing users on destination: {users}".format(
                n=len(users_missing_on_dst),
                users=", ".join(src_user_names[key]
                                for key in users_missing_on_dst))
            LOG.error(msg)
            raise cf_exceptions.AbortMigrationError(msg)

        LOG.info("All users are available on source, migration can proceed")
