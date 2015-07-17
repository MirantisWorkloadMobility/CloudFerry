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


from cloudferrylib.os.storage import cinder_database
from cloudferrylib.utils import utils


LOG = utils.get_log(__name__)


class CinderNetApp(cinder_database.CinderStorage):

    """Migration strategy used with NetApp multi backend.

    Extends `cinder_database` functionality with defining which volumes
    are stored on each particular NetApp server.

    NOTE: This is very (very!!!) custom implementation of Cinder storage with
    NFS NetApp backend. The reason to provide it was in different configuration
    of NetApp backend for Cinder on SRC and DST clouds in one case of
    migrations. It concerns 'host' attribute of volume. In SRC it looks like
    <host_name>, but in DST it should be as <host_name>@<NetApp_server_id>. And
    because of copying Cinder database data, standard NFS migration strategy
    (cloudferrylib.os.storage.cinder_database.CinderStorage) would not work in
    this particular case.

    To use this strategy - specify cinder_migration_strategy in config as
    'cloudferrylib.os.storage.cinder_netapp.CinderNetApp'.

    """

    def fix_entries(self, table_list_of_dicts, table_name):
        super(CinderNetApp, self).fix_entries(table_list_of_dicts, table_name)

        # Other tables do not contain 'host' column, so we do not change them
        if table_name != 'volumes':
            return

        for entry in table_list_of_dicts:
            entry[cinder_database.HOST] = self.make_hostname(entry)

    @staticmethod
    def make_hostname(entry):
        """ Make hostname in format <Host>@<NetApp_server_id>.

        :param entry: database record
        :return: new host
        :rtype: string
        """

        host = entry[cinder_database.HOST]
        location = entry['provider_location']

        if '@' in host:
            host = host.split('@')[0]

        netapp_server_id = location.split(':')[0]
        new_host = "%s@%s" % (host, netapp_server_id)

        LOG.debug("Change host entry for volume '%s' from '%s' to '%s'",
                  entry['id'], host, new_host)

        return new_host
