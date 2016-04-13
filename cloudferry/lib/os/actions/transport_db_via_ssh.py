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

from cloudferry.lib.base.action import transporter
from cloudferry.lib.os.actions import utils
from cloudferry.lib.utils import utils as utl


class TransportDbViaSsh(transporter.Transporter):
    # TODO: Use it with TaskTransfer, when is real usage example

    def run(self, cfg=None,
            src_cloud=None,
            dst_cloud=None,
            info_storage=None,
            resource_name=utl.VOLUMES_DB, **kwargs):
        data_for_trans = info_storage[resource_name]
        host_src = cfg.src_mysql.host
        host_dst = cfg.dst_mysql.host
        for item in data_for_trans:
            path_src = data_for_trans[item]
            path_dst = data_for_trans[item]
            utils.transfer_file_to_file(src_cloud, dst_cloud, host_src,
                                        host_dst, path_src, path_dst,
                                        cfg.migrate)
        return {}
