# Copyright 2016 Mirantis Inc.
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

import uuid as uuid_lib

from cloudferry.lib.utils import log

LOG = log.getLogger(__name__)


class CinderVolume(object):
    def __init__(self, uuid=None, display_name=None, provider_location=None,
                 project_id=None):
        self.id = uuid
        self.display_name = display_name
        self.provider_location = provider_location
        self.project_id = project_id

    def __repr__(self):
        s = "CinderVolume<uuid={id},display_name={name}>"
        return s.format(id=self.id, name=self.display_name)

    @classmethod
    def from_db_record(cls, volume):
        return cls(uuid=volume['id'],
                   display_name=volume['display_name'],
                   provider_location=volume['provider_location'],
                   project_id=volume['project_id'])


class CinderDBBroker(object):
    def __init__(self, mysql_connection):
        self.mysql = mysql_connection

    def get_cinder_volume(self, volume_id):
        """Provider location and extra specs are not available from APIs,
        yet is required for EMC VMAX volume migration."""
        get_volume = ('SELECT id, display_name, provider_location, project_id '
                      'FROM volumes WHERE id = :volume_id')
        volume = self.mysql.execute(get_volume, volume_id=volume_id).fetchone()

        if volume is not None:
            return CinderVolume.from_db_record(volume)

        LOG.debug("Volume '%s' not found!", volume_id)

    def _update_table(self, sql, old_id, parameters):
        sql = sql.format(', '.join('{0} = :{0}'.format(k)
                                   for k in parameters.keys()))
        parameters['old_id'] = old_id
        self.mysql.execute(sql, **parameters)

    def update_volume(self, old_id, **kwargs):
        sql = 'UPDATE volumes SET {} WHERE id = :old_id'
        self._update_table(sql, old_id, kwargs)

    def update_volume_metadata(self, old_id, **kwargs):
        sql = 'UPDATE volume_metadata SET {} WHERE volume_id = :old_id'
        self._update_table(sql, old_id, kwargs)

    def update_volume_id(self, old_id, new_id):
        with self.mysql.transaction():
            # It is impossible to update the primary key if any tables have
            # dependent records.
            # Making a copy of the fake volume with ID from source cloud.
            row = self.mysql.execute("SELECT * FROM volumes "
                                     "WHERE id = :old_id",
                                     old_id=old_id).fetchone()
            parameters = {'id': new_id}
            parameters.update({k: v for k, v in row.items() if k != 'id'})
            insert = "INSERT INTO volumes ({}) VALUES ({})".format(
                ', '.join(parameters.keys()),
                ', '.join(':{}'.format(k) for k in parameters.keys())
            )
            self.mysql.execute(insert, **parameters)

            # Update all dependent tables
            self.update_volume_metadata(old_id, volume_id=new_id)

            # Update an ID of fake volume to raise an exception if it still has
            # not updated dependent records in other tables
            fake_id = str(uuid_lib.uuid4())
            self.update_volume(old_id, id=fake_id)

            # Delete fake volume
            self.mysql.execute('DELETE FROM volumes WHERE id = :old_id',
                               old_id=fake_id)

    def inc_quota_usages(self, project_id, resource, value):
        self.mysql.execute("UPDATE quota_usages "
                           "SET in_use = in_use + :value "
                           "WHERE project_id = :project_id "
                           "AND resource = :resource",
                           project_id=project_id,
                           resource=resource,
                           value=value)
