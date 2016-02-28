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

from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


class CinderVolume(object):
    def __init__(self, uuid=None, display_name=None, provider_location=None):
        self.id = uuid
        self.display_name = display_name
        self.provider_location = provider_location

    def __repr__(self):
        s = "CinderVolume<uuid={id},display_name={name}>"
        return s.format(id=self.id, name=self.display_name)

    @classmethod
    def from_db_record(cls, volume):
        return cls(uuid=volume['id'],
                   display_name=volume['display_name'],
                   provider_location=volume['provider_location'])


class CinderDBBroker(object):
    def __init__(self, mysql_connection):
        self.mysql = mysql_connection

    def get_cinder_volume(self, volume_id):
        """Provider location and extra specs are not available from APIs,
        yet is required for EMC VMAX volume migration."""
        get_volume = ('SELECT id, display_name, provider_location '
                      'FROM volumes WHERE id = :volume_id')
        volume = self.mysql.execute(get_volume, volume_id=volume_id).fetchone()

        if volume is not None:
            return CinderVolume.from_db_record(volume)

        LOG.debug("Volume '%s' not found!", volume_id)
