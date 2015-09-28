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

__author__ = 'mirrorcoder'

DEFAULT = 0
NO_ELEMENT = -1


class Cursor(object):
    def __init__(self, net):
        self.net = net
        self.next_iter = None
        self.threads = []
        self.to_start()

    def next(self):
        if not self.next_iter:
            self.next_iter = self.net
            self.threads = [i for i in self.next_iter.parall_elem]
        else:
            if self.threads:
                return self.threads.pop()
            if self.next_iter.next_element[0]:
                if self.next_iter.num_element < len(
                        self.next_iter.next_element):
                    self.__change_state_cursor(self.next_iter.num_element)
                else:
                    self.__change_state_cursor(DEFAULT)
            else:
                self.next_iter = NO_ELEMENT
        if self.next_iter == NO_ELEMENT:
            raise StopIteration
        return self.next_iter

    def __change_state_cursor(self, num_element):
        self.next_iter = self.next_iter.next_element[num_element]
        self.threads = [i for i in self.next_iter.parall_elem]

    def __iter__(self):
        return self

    def current(self):
        return self.net

    @staticmethod
    def forward_back(net):
        obj = net
        while obj.prev_element:
            obj = obj.prev_element
        return obj

    def to_start(self):
        obj = self.forward_back(self.net)
        self.net = obj
        self.next_iter = None
        return obj
