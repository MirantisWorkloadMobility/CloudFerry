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

from cloudferry.lib.scheduler.task import Task
from cloudferry.lib.scheduler.utils.equ_instance import EquInstance

HIGH = 3
NORMAL = 2
LOW = 1


class WrapThreadTask(EquInstance):
    def __init__(self, net=None, priority=None):
        self.net = net
        self.priority = priority
        self.class_name = WrapThreadTask.__name__

    def getNet(self):
        return self.net


class WaitThreadTask(Task):
    def __init__(self, tt):
        self.tt = tt
        super(WaitThreadTask, self).__init__()

    def run(self, __children__=None, **kwargs):
        if __children__:
            __children__[self.tt]['process'].join()


class WaitThreadAllTask(Task):
    def run(self, __children__=None, **kwargs):
        if __children__:
            for p in __children__:
                __children__[p]['process'].join()
