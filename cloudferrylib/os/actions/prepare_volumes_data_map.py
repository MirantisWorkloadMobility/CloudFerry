
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


from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl
import copy


class PrepareVolumesDataMap(action.Action):

    def __init__(self, init, src_vol_info_name, dst_vol_info_name):
        super(PrepareVolumesDataMap, self).__init__(init)
        self.src_vol_info_name = src_vol_info_name
        self.dst_vol_info_name = dst_vol_info_name

    def run(self, **kwargs):
        volumes_data_map = {}
        src_vol_info = kwargs[self.src_vol_info_name]
        dst_vol_info = kwargs[self.dst_vol_info_name]
        src_storage_info = copy.deepcopy(src_vol_info)
        src_volumes = src_storage_info[utl.VOLUMES_TYPE]
        dst_storage_info = copy.deepcopy(dst_vol_info)
        dst_volumes = dst_storage_info[utl.VOLUMES_TYPE]

        for dst_id, vol in dst_volumes.iteritems():
            src_id = vol[utl.OLD_ID]
            src_host = src_volumes[src_id][utl.VOLUME_BODY]['host']
            src_path = src_volumes[src_id][utl.VOLUME_BODY]['path']
            dst_host = vol[utl.VOLUME_BODY]['host']
            dst_path = vol[utl.VOLUME_BODY]['path']
            volumes_data_map[dst_id] = vol
            volumes_data_map[dst_id][utl.OLD_ID] = src_id
            volumes_data_map[dst_id][utl.VOLUME_BODY].update({
                utl.HOST_SRC: src_host,
                utl.PATH_SRC: src_path,
                utl.HOST_DST: dst_host,
                utl.PATH_DST: dst_path
            })
            volumes_data_map[dst_id][utl.META_INFO].\
                update(src_volumes[src_id][utl.META_INFO])
        volumes = {
            utl.VOLUMES_TYPE: volumes_data_map
        }

        return {
            'storage_info': volumes
        }
