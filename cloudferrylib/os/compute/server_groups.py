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
"""
This module contains the logic for collecting server group information from a
cloud and deploying server groups on a cloud.

Example:
    src_handler = Handler(src_cloud)
    dst_handler = Handler(dst_cloud)
    dst_handler.deploy_server_groups(src_handler.get_server_groups())
"""

import pprint

from novaclient import exceptions as nova_exc

from cloudferrylib.base.resource import Resource
from cloudferrylib.utils import utils as utl


LOG = utl.get_log(__name__)

SQL_SELECT_ALL_GROUPS = ("SELECT user_id, project_id, uuid, name, id FROM "
                         "instance_groups WHERE deleted=0;")
SQL_SELECT_POLICY = ("SELECT policy FROM instance_group_policy WHERE "
                     "group_id=%s AND deleted=0;")
SQL_SELECT_GROUP_ID = "SELECT id FROM instance_groups WHERE uuid='{0}';"
SQL_DELETE_MEMBER = "DELETE FROM instance_group_member WHERE group_id={0};"
SQL_DELETE_POLICY = "DELETE FROM instance_group_member WHERE group_id={0};"
SQL_DELETE_GROUP = "DELETE_FROM instance_groups WHERE uuid='{0}';"
SQL_INSERT_GROUP = ("INSERT INTO instance_groups (uuid, name, project_id, "
                    "user_id, deleted) VALUES('{0}', '{1}', '{2}', '{3}', 0);")
SQL_INSERT_POLICY = ("INSERT INTO instance_group_policy (group_id, policy, "
                     "deleted) VALUES({0}, '{1}', 0)")


class Handler(Resource):
    """
    Handler for Nova Server/Instance Groups on specified cloud.
    Allows for collection, creation and duplicate detection.
    """

    def __init__(self, cloud):
        super(Handler, self).__init__()
        self.cloud = cloud
        self.compute = self.cloud.resources[utl.COMPUTE_RESOURCE]

    def _execute(self, sql):
        """
        Logs SQL statement and executes using mysql connector from
        COMPUTE_RESOURCE
        """
        LOG.debug("SQL statement: %s", sql)
        return self.compute.mysql_connector.execute(sql)

    @property
    def _nova_client(self):
        """
        Property than returns COMPUTE_RESOURCE nova client
        """
        return self.compute.nova_client

    def get_server_groups(self):
        """
        Return list of dictionaries containing server group details

        Returns:
            list: Empty if no server groups exist or server groups are not
                supported

            [
                {
                    "user": "<user name>",
                    "tenant": "<tenant name>",
                    "uuid": "<group uuid>",
                    "name": "<group name>",
                    "policies": [<policy_name>, ...]
                }
            ]
        """
        groups = []
        try:
            self._nova_client.server_groups.list()

            identity_res = self.cloud.resources[utl.IDENTITY_RESOURCE]

            for row in self._execute(SQL_SELECT_ALL_GROUPS).fetchall():
                print "1", row
                sql = SQL_SELECT_POLICY % row[4]
                policies = []
                for policy in self._execute(sql).fetchall():
                    policies.append(policy[0])
                groups.append(
                    {"user": identity_res.try_get_username_by_id(row[0]),
                     "tenant": identity_res.try_get_tenant_name_by_id(row[1]),
                     "uuid": row[2],
                     "name": row[3],
                     "policies": policies})
        except nova_exc.NotFound:
            LOG.info("Cloud does not support server_groups")
        return groups

    def _delete_server_group(self, server_group):
        """
        Uses the sql connector to do the following:
            Retrieves the appropriate group id using the groups UUID
            Removes associated members
            Removes associated policies
            Removes group itself
        """

        sql = SQL_SELECT_GROUP_ID.format(server_group['uuid'])
        gid = self._execute(sql).fetchone()[0]

        sql = SQL_DELETE_MEMBER.format(gid)
        self._execute(sql)

        sql = SQL_DELETE_POLICY.format(gid)
        self._execute(sql)

        sql = SQL_DELETE_GROUP.format(server_group['uuid'])
        self._execute(sql)

    def deploy_server_groups(self, src_groups):
        """
        For each server groups in source cloud, UUID is checked for existence
        in destination cloud.
        If not existing the server group is created.
        If UUID matches a comparison is made and if there is a difference the
        server group is deleted and recreated.
        If UUID matches a comparison is made and there is no differences the
        group is skipped.
        """
        dst_groups = self.get_server_groups()
        for src_group in src_groups:
            LOG.debug("Source HOST server_groups: %s",
                      pprint.pformat(src_group))
            dst_exists = False
            for dst_group in dst_groups:
                LOG.debug("Destination HOST server_groups: %s",
                          pprint.pformat(dst_group))
                if src_group['uuid'] == dst_group['uuid']:
                    if _compare_groups(src_group, dst_group):
                        LOG.info("skipping matching server_group in "
                                 "destination: %s", src_group['name'])
                        dst_exists = True
                    else:
                        LOG.info("deleting server_group collision "
                                 "in destination: %s", dst_group['name'])
                        self._delete_server_group(dst_group)
            if not dst_exists:
                self._deploy_server_group(src_group)

    def _deploy_server_group(self, server_group):
        """
        Uses the sql connector to do the following:
            Inserts specified uuid, name, tenant uuid and user uuid into
            destination cloud.
            Retrieves internally incremented group id
            Inserts associated policies using group id

        """
        LOG.info("Deploying server_group for tenant %s to destination: %s",
                 server_group['tenant'], server_group['name'])

        identity_res = self.cloud.resources[utl.IDENTITY_RESOURCE]

        sql = SQL_INSERT_GROUP.format(
            server_group['uuid'],
            server_group['name'],
            identity_res.get_tenant_id_by_name(server_group["tenant"]),
            identity_res.try_get_user_by_name(server_group["user"]).id,
        )
        self._execute(sql)

        sql = SQL_SELECT_GROUP_ID.format(server_group['uuid'])
        gid = self._execute(sql).fetchone()[0]
        for policy in server_group['policies']:
            sql = SQL_INSERT_POLICY.format(gid, policy)
            self._execute(sql)

        return server_group


def _compare_groups(group_a, group_b):
    """
    Compares server group_a with server_group b

    Returns:
        bool: True if specified values are equal, otherwise false
    """

    return (group_a['policies'] == group_b['policies'] and
            group_a['tenant'] == group_b['tenant'] and
            group_a['name'] == group_b['name'] and
            group_a['user'] == group_b['user'] and
            group_a['policies'] == group_b['policies'])
