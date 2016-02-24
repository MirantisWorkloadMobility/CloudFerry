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
from cloudferrylib.utils import log
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import ssh_util
from fabric.api import local


LOG = log.getLogger(__name__)


class MysqlDump(action.Action):
    """Dumps MySQL database to a file. Primarily used for rollbacks.

    Config options:
      - `config.migrate.mysqldump_host`;
      - `config.dst_mysql.db_host` - used if `config.migrate.mysqldump_host` is
        not set.

    Process:
      1. SSH into DB host (see Config options);
      2. Run `mysqldump`;
      3. Copy MySQL dump to CloudFerry host.

    Requirements:
      - SSH access to DB host (see Config options);
      - Read access to MySQL DB from DB host;
      - Write access for `config.dst_mysql.db_user` on DB host.
    """

    def run(self, *args, **kwargs):
        db_host = mysql_connector.get_db_host(self.cloud.cloud_config)

        # dump mysql to file
        # probably, we have to choose what databases we have to dump
        # by default we dump all databases
        options = ["--user={user}", "--opt", "--all-databases"]
        if self.cloud.cloud_config.mysql.db_password:
            options.append("--password={password}")
        options = " ".join(options).format(
            user=self.cloud.cloud_config.mysql.db_user,
            password=self.cloud.cloud_config.mysql.db_password
        )
        command = "mysqldump {options} > {path}".format(
            options=options,
            path=self.cloud.cloud_config.snapshot.snapshot_path
        )
        LOG.info("dumping database with command '%s'", command)
        self.cloud.ssh_util.execute(command, host_exec=db_host)
        # copy dump file to host with cloudferry (for now just in case)
        # in future we will store snapshot for every step of migration
        key_string = ' -i '.join(self.cloud.config.migrate.key_filename)

        context = {
            'host_src': db_host,
            'path_src': self.cloud.cloud_config.snapshot.snapshot_path,
            'user_src': self.cloud.cloud_config.cloud.ssh_user,
            'key': key_string,
            'path_dst': self.cloud.cloud_config.snapshot.snapshot_path,
            'cipher': ssh_util.get_cipher_option(),
        }
        command = (
            "scp {cipher} -o StrictHostKeyChecking=no -i {key} "
            "{user_src}@{host_src}:{path_src} {path_dst}".format(**context))
        LOG.info("EXECUTING {command} local".format(command=command))
        local(command)
        return {}


class MysqlRestore(action.Action):
    """Restores MySQL DB from previously created dump using `MysqlDump()`

    See `MysqlDump` documentation for requirements and config options used.
    """

    def run(self, *args, **kwargs):
        db_host = mysql_connector.get_db_host(self.cloud.cloud_config)

        # apply sqldump from file to mysql
        options = ["--user={user}"]
        if self.cloud.cloud_config.mysql.db_password:
            options.append("--password={password}")
        options = " ".join(options).format(
            user=self.cloud.cloud_config.mysql.db_user,
            password=self.cloud.cloud_config.mysql.db_password
        )
        command = "mysql {options} < {path}".format(
            options=options,
            path=self.cloud.cloud_config.snapshot.snapshot_path
        )
        LOG.info("restoring database with command '%s'", command)
        self.cloud.ssh_util.execute(command, host_exec=db_host)
        return {}
