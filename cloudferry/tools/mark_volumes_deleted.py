# Copyright (c) 2016 Mirantis Inc.
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

import logging

from cloudferry.lib.os.storage import cinder_db
from cloudferry.lib.utils import mysql_connector

LOG = logging.getLogger(__name__)


def mark_volumes_deleted(config, volume_ids):
    def get_opt(name):
        return (getattr(config.src_storage, name) or
                getattr(config.src_mysql, name))
    db_config = {opt: get_opt(opt) for opt in ('db_user', 'db_password',
                                               'db_host', 'db_port',
                                               'db_connection')}
    db_name = config.src_storage.db_name
    conn = mysql_connector.MysqlConnector(db_config, db_name)
    src_db = cinder_db.CinderDBBroker(conn)
    result = []
    with conn.transaction():
        for volume_id in volume_ids:
            volume = src_db.get_cinder_volume(volume_id)
            if volume is None:
                LOG.error("Volume '%s' not found.", volume_id)
                result.append((volume_id, None, 'not found'))
                continue
            if volume.deleted:
                LOG.warning("Volume '%s' is already deleted.", volume_id)
                result.append((volume.id, volume.deleted_at, 'skipped'))
                continue
            LOG.debug("Mark volume '%s' as deleted.", volume_id)
            volume = src_db.delete_volume(volume_id)
            result.append((volume.id, volume.deleted_at, 'deleted'))
    return result
