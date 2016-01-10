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


"""
This module contains actions for retrieving server groups and their policies
from a source cloud and deploying them into a destination cloud
"""


from cloudferrylib.base.action import transporter
from cloudferrylib.os.compute import server_groups
from cloudferrylib.utils import log


LOG = log.getLogger(__name__)


class ServerGroupTransporter(transporter.Transporter):
    """
    Transporter uses server group handlers to retrieve and deploy server
    groups in from defined cloud.

    Required configuration options:
        [src]
        type = os
        auth_url = http://<auth_url>
        user = <admin_user>
        password = <admin_pass>
        tenant = <admin_tenant>

        [dst]
        type = os
        auth_url = http://<auth_url>
        user = <admin_user>
        password = <admin_pass>
        tenant = <admin_tenant>

        [src_compute]
        service = nova
        db_connection = mysql+pymysql
        db_host = <db_host>
        db_port = <db_port>
        db_name = nova
        db_user = <db_user>
        db_password = <db_password>

        [dst_compute]
        service = nova
        db_connection = mysql+pymysql
        db_host = <db_host>
        db_port = <db_port>
        db_name = nova
        db_user = <db_user>
        db_password = <db_password>

    Scenario:
        process:
            - task_server_group_transport:
                -act_server_group_trans: True

    Dependent tasks:
        None
    Required tasks:
        None
    """

    def run(self, **kwargs):
        src_resource = server_groups.ServerGroupsHandler(self.src_cloud)
        dst_resource = server_groups.ServerGroupsHandler(self.dst_cloud)
        src_server_groups = src_resource.get_server_groups()
        if len(src_server_groups) > 0:
            dst_resource.deploy_server_groups(src_server_groups)
        else:
            LOG.debug("No server groups found on the source cloud")
        return {'server_group_info': src_server_groups}
