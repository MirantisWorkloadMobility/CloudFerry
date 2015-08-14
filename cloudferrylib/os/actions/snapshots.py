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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils
from fabric.api import local


LOG = utils.get_log(__name__)


class MysqlDump(action.Action):

    def run(self, *args, **kwargs):
        # dump mysql to file
        # probably, we have to choose what databases we have to dump
        # by default we dump all databases
        command = ("mysqldump "
                   "--user={user} "
                   "--password={password} "
                   "--opt "
                   "--all-databases > {path}").format(
            user=self.cloud.cloud_config.mysql.user,
            password=self.cloud.cloud_config.mysql.password,
            path=self.cloud.cloud_config.snapshot.snapshot_path)
        LOG.info("dumping database with command '%s'", command)
        self.cloud.ssh_util.execute(command)
        # copy dump file to host with cloudferry (for now just in case)
        # in future we will store snapshot for every step of migration
        context = {
            'host_src': self.cloud.cloud_config.mysql.host,
            'path_src': self.cloud.cloud_config.snapshot.snapshot_path,
            'user_src': self.cloud.cloud_config.cloud.ssh_user,
            'key': self.cloud.config.migrate.key_filename,
            'path_dst': self.cloud.cloud_config.snapshot.snapshot_path}
        command = (
            "scp -o StrictHostKeyChecking=no -i {key} "
            "{user_src}@{host_src}:{path_src} {path_dst}".format(**context))
        LOG.info("EXECUTING {command} local".format(command=command))
        local(command)
        return {}


class MysqlRestore(action.Action):

    def run(self, *args, **kwargs):
        # apply sqldump from file to mysql
        command = ("mysql "
                   "--user={user} "
                   "--password={password} "
                   "< {path}").format(
            user=self.cloud.cloud_config.mysql.user,
            password=self.cloud.cloud_config.mysql.password,
            path=self.cloud.cloud_config.snapshot.snapshot_path)
        LOG.info("restoring database with command '%s'", command)
        self.cloud.ssh_util.execute(command)
        return {}
