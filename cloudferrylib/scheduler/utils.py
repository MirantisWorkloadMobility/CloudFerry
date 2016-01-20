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

from base import begin_task, end_task


def chain(net=None):
    b_t = begin_task.BeginTask()
    e_t = end_task.EndTask()
    if net:
        net.go_end() >> e_t
        b_t >> net.go_begin()
    return b_t, e_t
