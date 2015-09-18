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
import copy
__author__ = 'mirrorcoder'

CHILDREN = '__children__'


class Namespace:

    def __init__(self, vars={}):
        if CHILDREN not in vars:
            vars[CHILDREN] = dict()
        self.vars = vars

    def fork(self, is_deep_copy=False):
        return Namespace(copy.copy(self.vars)) if not is_deep_copy \
            else Namespace(copy.deepcopy(self.vars))
