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


from cloudferrylib.scheduler import task


class Action(task.Task):

    def __init__(self, init, cloud=None):
        self.cloud = None
        self.src_cloud = None
        self.dst_cloud = None
        self.cfg = None
        self.__dict__.update(init)
        self.init = init
        if cloud:
            self.cloud = init[cloud]
        super(Action, self).__init__()

    def run(self, **kwargs):
        pass

    def save(self):
        pass

    def restore(self):
        pass
