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

from Cloud import Cloud
from resources.NovaCompute import NovaCompute
from CloudFerry import CloudFerry
__author__ = 'mirrorcoder'


class OS2OSFerry(CloudFerry):

    def __init__(self, config):
        super(OS2OSFerry, self). __init__(config)
        self.src_cloud = Cloud(NovaCompute(), )
        self.dst_cloud = Cloud(NovaCompute(), )
        self.src_cloud.auth(config['source'])
        self.dst_cloud.auth(config['destination'])
