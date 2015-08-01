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


from cloudferrylib.base.action import transporter
from cloudferrylib.utils import utils as utl


class IdentityTransporter(transporter.Transporter):

    def run(self, **kwargs):
        search_opts = kwargs.get('search_opts_tenant', {})
        src_resource = self.src_cloud.resources[utl.IDENTITY_RESOURCE]
        dst_resource = self.dst_cloud.resources[utl.IDENTITY_RESOURCE]
        info = src_resource.read_info(**search_opts)
        dst_resource.deploy(info)
        return {'identity_info': info}
