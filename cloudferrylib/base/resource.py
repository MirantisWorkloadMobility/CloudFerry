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


class Resource(object):
    def __init__(self):
        pass

    def read_info(self, opts={}):
        pass

    def deploy(self, *args):
        pass

    def save(self):
        pass

    def restore(self):
        pass

    def wait_for_status(self, id_obj, status, limit_retry=60):
        pass

    def get_status(self):
        pass

    def __deepcopy__(self, memo):
        return self
