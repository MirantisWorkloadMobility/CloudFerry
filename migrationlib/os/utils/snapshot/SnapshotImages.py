# Copyright (c) 2014 Mirantis Inc.
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
from SnapshotState import SnapshotState
from Snapshot import Snapshot
__author__ = 'mirrorcoder'


class SnapshotImages(SnapshotState):
    def create_snapshot(self):
        snapshot = Snapshot()
        [snapshot.addImage(id=image.id,
                           disk_format=image.disk_format,
                           name=image.name,
                           checksum=image.checksum)
         for image in self.glance_client.images.list()]
        return snapshot
