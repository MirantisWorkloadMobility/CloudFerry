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
import keystoneclient
import mock
from cloudferrylib.os.compute import keypairs

from tests import test
from cloudferrylib.os.actions import transport_compute_resources as tcr
from cloudferrylib.utils import utils as utl


class KeyPairObjectTestCase(test.TestCase):
    def test_key_pair_does_not_include_autoincrement_fields(self):
        kp_db = (
            "Jan 1st 1970",       # created_at
            None,                 # updated_at
            None,                 # deleted_at
            "keypair-id",         # id
            "keypair-name",       # name
            "user-id",            # user_id
            "aa:bb:cc:dd:ee:ff",  # fingerprint
            "public-key-data",    # public_key
            0,                    # deleted
        )
        kp = keypairs.KeyPair.from_tuple(kp_db)
        kp_dict = kp.to_dict(allow_auto_fields=False)
        self.assertTrue('id' not in kp_dict.keys())

    def test_all_fields_are_accessible_through_attributes(self):
        kp = keypairs.KeyPair()

        try:
            for field in kp.FIELDS:
                getattr(kp, field)
        except AttributeError:
            self.fail("KeyPair object must have all fields accessible as "
                      "attributes")

    def test_value_error_is_risen_in_case_db_value_is_incorrect(self):
        # user id, fingerprint, public key and deleted keys missing
        db_kp = ("datetime", None, None, "id", "keypair name")
        self.assertRaises(ValueError, keypairs.KeyPair.from_tuple, db_kp)

        db_kp = ("datetime", None, None, "id", "keypair name", "user id",
                 "fingerprint", "public key", 0, "invalid argument")
        self.assertRaises(ValueError, keypairs.KeyPair.from_tuple, db_kp)

    def test_fields_are_settable_as_attributes(self):
        try:
            kp = keypairs.KeyPair()

            public_key_value = "random public key"
            fingerprint_value = "fingerprint"
            deleted_value = 1

            kp.public_key = public_key_value
            kp.fingerprint = fingerprint_value
            kp.deleted = deleted_value

            self.assertEqual(kp.public_key, public_key_value)
            self.assertEqual(kp.fingerprint, fingerprint_value)
            self.assertEqual(kp.deleted, deleted_value)
        except AttributeError:
            self.fail("Key pair fields must be settable as attributes")

    def test_key_pair_has_dict_support(self):
        try:
            kp = keypairs.KeyPair()

            public_key_value = "random public key"
            fingerprint_value = "fingerprint"
            deleted_value = 1

            kp['public_key'] = public_key_value
            kp['fingerprint'] = fingerprint_value
            kp['deleted'] = deleted_value

            self.assertEqual(kp['public_key'], public_key_value)
            self.assertEqual(kp['fingerprint'], fingerprint_value)
            self.assertEqual(kp['deleted'], deleted_value)
        except KeyError:
            self.fail("Key pair fields must be settable as dict item")


class KeyPairMigrationTestCase(test.TestCase):
    @mock.patch('cloudferrylib.os.identity.keystone.'
                'get_dst_user_from_src_user_id')
    def test_non_existing_user_does_not_break_migration(self, _):
        try:
            db_broker = mock.Mock()
            db_broker.get_all_keypairs.return_value = [keypairs.KeyPair(),
                                                       keypairs.KeyPair()]

            tkp = tcr.TransportKeyPairs(init=mock.MagicMock(),
                                        kp_db_broker=db_broker)

            tkp.src_cloud = mock.MagicMock()
            tkp.dst_cloud = mock.MagicMock()
            tkp.cfg = mock.Mock()
            tkp.cfg.migrate.skip_orphaned_keypairs = True

            src_users = tkp.src_cloud.resources[
                utl.IDENTITY_RESOURCE].keystone_client.users
            src_users.find.side_effect = keystoneclient.exceptions.NotFound

            dst_users = tkp.dst_cloud.resources[
                utl.IDENTITY_RESOURCE].keystone_client.users
            dst_users.find.side_effect = keystoneclient.exceptions.NotFound

            tkp.run()
        except Exception as e:
            self.fail("Unexpected exception caught: %s" % e)

    def test_update_sql_gets_called_for_each_keypair(self):
        num_keypairs = 5

        db_broker = mock.Mock()
        db_broker.get_all_keypairs.return_value = [
            keypairs.KeyPair() for _ in xrange(num_keypairs)]
        db_broker.store_keypair = mock.Mock()

        tkp = tcr.TransportKeyPairs(init=mock.MagicMock(),
                                    kp_db_broker=db_broker)
        tkp.src_cloud = mock.MagicMock()
        tkp.dst_cloud = mock.MagicMock()
        tkp.cfg = mock.Mock()
        tkp.cfg.migrate.skip_orphaned_keypairs = True

        tkp.run()

        self.assertTrue(db_broker.store_keypair.call_count == num_keypairs)


class KeyPairForInstancesTestCase(test.TestCase):
    def test_does_nothing_if_no_info_provided(self):
        db_broker = mock.Mock()
        task = tcr.SetKeyPairsForInstances(init=mock.MagicMock(),
                                           kp_db_broker=db_broker)
        task.run()

        self.assertFalse(db_broker.add_keypair_to_instance.called)

    def test_keypair_is_added_to_instance(self):
        db_broker = mock.Mock()

        num_instances_with_keys = 5
        num_instances_without_keys = 5

        instances = {
            'instance1%d' % i: {
                'instance': {
                    'key_name': 'key%d' % i,
                    'user_id': 'user%d' % i
                }
            } for i in xrange(num_instances_with_keys)
        }

        instances.update({
            'instance2%d' % j: {
                'instance': {
                    'user_id': 'user%d' % j
                }
            } for j in xrange(num_instances_without_keys)}
        )

        info = {utl.INSTANCES_TYPE: instances}

        task = tcr.SetKeyPairsForInstances(init=mock.MagicMock(),
                                           kp_db_broker=db_broker)
        task.run(info=info)

        self.assertTrue(db_broker.add_keypair_to_instance.called)
        self.assertEqual(db_broker.add_keypair_to_instance.call_count,
                         num_instances_with_keys)
