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


import copy

from cloudferrylib.utils import sizeof_format
from cloudferrylib.utils import log

LOG = log.getLogger(__name__)


class CinderStorageMigrationProgressView(object):

    """ View to show the progress of volumes migration. """

    def __init__(self, src_volumes, dst_volumes, volumes_size_map):
        self.src_volumes = copy.deepcopy(src_volumes)
        self.dst_volumes = copy.deepcopy(dst_volumes)
        self.failed_volumes = []
        self.volumes_size_map = volumes_size_map
        self.avg_speed_mb_s = 0
        self.num_migrated = 0

        self.total_vol_size_b = 0
        self.migrated_vol_size_b = 0
        self.failed_vol_size_b = 0
        for v_id, v_size in self.volumes_size_map.iteritems():
            self.total_vol_size_b += v_size
            if v_id in self.dst_volumes:
                self.migrated_vol_size_b += v_size

    def show_stats(self):
        if len(self.dst_volumes) > 0:
            LOG.info('Total number of volumes already '
                     'migrated to destenation cloud: %d',
                     len(self.dst_volumes))

            LOG.info('Volumes already migrated:\n%s',
                     '\n'.join([
                         "%s(%s)" % (v['display_name'], v['id'])
                         for v in self.dst_volumes]))

        LOG.info('Total number of volumes to be migrated: %d',
                 len(self.src_volumes))
        LOG.info('List of volumes to be migrated:\n%s',
                 '\n'.join([
                      "%s(%s)" % (v['display_name'], v['id'])
                      for v in self.src_volumes]))

    def sync_migrated_volumes_info(self, volume, elapsed_time):
        LOG.info('Volume %s(%s) has been successfully migrated.',
                 volume.get('display_name', ''),
                 volume['id'])
        self.num_migrated += 1
        volume_size_b = self.volumes_size_map[volume['id']]
        self.migrated_vol_size_b += volume_size_b

        if elapsed_time == 0:
            self.avg_speed_mb_s = 0
        else:
            self.avg_speed_mb_s = (volume_size_b/(1024.0**2))/elapsed_time

    def sync_failed_volumes_info(self, volume):
        LOG.warning('Copying volume %s(%s) failed.',
                    volume.get('display_name', ''),
                    volume['id'])
        self.failed_vol_size_b += self.volumes_size_map[volume['id']]
        self.failed_volumes.append(volume)

    def show_progress(self):
        LOG.info('Number of migrated volumes %d of %d. '
                 'Volumes migrated %.1f%% and '
                 'failed %.1f%% of %s total at %.1f MB/s.',
                 self.num_migrated,
                 len(self.src_volumes) + len(self.dst_volumes),
                 float(self.migrated_vol_size_b) / self.total_vol_size_b * 100,
                 float(self.failed_vol_size_b) / self.total_vol_size_b * 100,
                 sizeof_format.sizeof_fmt(self.total_vol_size_b),
                 self.avg_speed_mb_s)
