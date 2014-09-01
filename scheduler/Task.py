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

from Namespace import Namespace

__author__ = 'mirrorcoder'


class Task(object):
    def __init__(self, namespace=Namespace()):
        self.namespace = namespace

    def __call__(self, namespace=None):
        namespace = self.namespace if not namespace else namespace
        result = self.run(**namespace.vars)
        namespace.vars.update(result)

    def __hash__(self):
        return hash(Task.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        return "Task|%s" % self.__class__.__name__
