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

from Task import Task
import time
__author__ = 'mirrorcoder'


class Action(Task):
    def __init__(self, a):
        self.a = a
        super(Action, self).__init__()

    def run(self, **kwargs):
        import random
        time.sleep(random.randint(0, 5))
        print self.a


class ThreadAction(Task):
    def __init__(self, a):
        self.a = a
        super(ThreadAction, self).__init__()

    def run(self, **kwargs):

        time.sleep(3)
        print self.a


class CondAction(Task):
    def __init__(self, a):
        self.a = a
        super(CondAction, self).__init__()

    def run(self, **kwargs):
        import random
        time.sleep(random.randint(0, 5))
        print self.a
        self.set_next_path(2)