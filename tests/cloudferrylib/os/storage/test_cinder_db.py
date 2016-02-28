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

from tests import test

from cloudferrylib.os.storage import cinder_db


class CinderVolumeTestCase(test.TestCase):
    def test_has_uuid_attribute(self):
        v = cinder_db.CinderVolume()
        self.assertTrue(hasattr(v, "id"))

    def test_has_display_name_attribute(self):
        v = cinder_db.CinderVolume()
        self.assertTrue(hasattr(v, "display_name"))

    def test_has_provider_location_attribute(self):
        v = cinder_db.CinderVolume()
        self.assertTrue(hasattr(v, "provider_location"))
