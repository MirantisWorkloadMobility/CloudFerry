# Copyright 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cloudferrylib.utils import log
from cloudferrylib.utils import utils as utl


LOG = log.getLogger(__name__)


class KeyPair(dict):
    """Represents nova key pair based on DB schema:
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
    """

    FIELDS = ['created_at', 'updated_at', 'deleted_at', 'id', 'name',
              'user_id', 'fingerprint', 'public_key', 'deleted']
    AUTO_FIELDS = ['id']

    def __init__(self, **kwargs):
        super(KeyPair, self).__init__(**kwargs)
        for field in self.FIELDS:
            value = kwargs.get(field)
            setattr(self, field, value)
            self[field] = value

    @classmethod
    def from_tuple(cls, fetched_data):
        """Builds KeyPair object from sqlalchemy-returned tuple"""
        if len(fetched_data) != len(cls.FIELDS):
            raise ValueError("Invalid value provided to KeyPair")

        kp = KeyPair()
        for i, key in enumerate(cls.FIELDS):
            setattr(kp, key, fetched_data[i])
        return kp

    def to_dict(self, allow_auto_fields=False):
        d = {}
        fields = (self.FIELDS
                  if allow_auto_fields
                  else filter(lambda s: s not in self.AUTO_FIELDS,
                              self.FIELDS))
        for key in fields:
            if getattr(self, key) is not None:
                d[key] = getattr(self, key)
        return d


class DBBroker(object):
    """Defines DB methods. Moved to a class to ease unit tests mocking."""

    NOVA_KEYPAIRS = "nova.key_pairs"
    NOVA_INSTANCES = "nova.instances"

    @classmethod
    def get_all_keypairs(cls, cloud):
        db = DBBroker._get_db(cloud)
        sql = "SELECT * FROM {key_pairs} WHERE deleted = 0;".format(
            key_pairs=cls.NOVA_KEYPAIRS)
        return map(KeyPair.from_tuple, db.execute(sql).fetchall())

    @classmethod
    def store_keypair(cls, key_pair, cloud):
        db = DBBroker._get_db(cloud)

        key_pair_dict = key_pair.to_dict()
        kp_fields = str(key_pair.to_dict().keys()).translate(None, "[]'")
        kp_values = ','.join(['"{}"'.format(kp)
                              for kp in key_pair_dict.values()])

        sql = ("INSERT INTO {nova_keypairs} ({fields}) "
               "VALUES ({values}) ON DUPLICATE KEY UPDATE id=id;"
               ).format(nova_keypairs=cls.NOVA_KEYPAIRS,
                        fields=kp_fields,
                        values=kp_values)

        LOG.info("Storing keypair '%s' in DB", key_pair.name)
        LOG.debug(sql)

        db.execute(sql)

    @classmethod
    def add_keypair_to_instance(cls, cloud, key_name, user_id, instance_id):
        db = DBBroker._get_db(cloud)

        sql = ("UPDATE {instances} "
               "INNER JOIN {key_pairs} "
               "ON {instances}.user_id = {key_pairs}.user_id "
               "   AND {instances}.uuid='{instance_id}' "
               "   AND {key_pairs}.user_id='{user_id}' "
               "   AND {instances}.user_id='{user_id}' "
               "   AND {instances}.deleted = 0 "
               "   AND {key_pairs}.deleted = 0 "
               "SET {instances}.key_name='{key_name}', "
               "    {instances}.key_data={key_pairs}.public_key;"
               ).format(
            instances=cls.NOVA_INSTANCES,
            key_pairs=cls.NOVA_KEYPAIRS,
            key_name=key_name,
            user_id=user_id,
            instance_id=instance_id)

        LOG.info("Adding keypair '%s' to instance '%s'", key_name, instance_id)
        LOG.debug(sql)

        db.execute(sql)

    @classmethod
    def _get_db(cls, cloud):
        return cloud.resources[utl.COMPUTE_RESOURCE].mysql_connector
