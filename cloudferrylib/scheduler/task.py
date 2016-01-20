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

from cloudferrylib.scheduler.cursor import DEFAULT
from cloudferrylib.scheduler.utils.equ_instance import EquInstance

START = 0
END = 0


class Element(object):
    def __init__(self):
        self.prev_element = None
        self.next_element = [None]
        self.parall_elem = []
        self.num_element = DEFAULT

    def set_next_path(self, num):
        self.num_element = num

    def go(self, delta):
        if delta == START:
            return self.go_start()
        if delta == END:
            return self.go_end()

    def go_start(self):
        elem = self
        while elem.prev_element:
            elem = elem.prev_element
        return elem

    def go_end(self):
        elem = self
        while elem.next_element[0]:
            elem = elem.next_element[0]
        return elem


class ClassicSyntax(Element):
    def add_closure_link_with(self, other):
        self.next_element[0] = other
        return self

    def add_another_link_with(self, other):
        self.next_element.append(other)
        return self

    def add_thread(self, other):
        self.parall_elem.append(other)
        return self

    def dual_link_with(self, other):
        other = other.go_start()
        self.next_element[0] = other
        other.prev_element = self if not other.prev_element \
            else other.prev_element
        return other.go_end()


class AltSyntax(ClassicSyntax):
    def __sub__(self, other):
        return self.add_closure_link_with(other)

    def __or__(self, other):
        return self.add_another_link_with(other)

    def __and__(self, other):
        return self.add_thread(other)

    def __rshift__(self, other):
        return self.dual_link_with(other)


class BaseTask(AltSyntax, EquInstance):

    def __init__(self):
        self.class_name = BaseTask.__name__
        super(BaseTask, self).__init__()

    def run(self, **kwargs):
        pass

    def __call__(self, namespace=None):
        result = self.run(**namespace.vars)
        if type(result) == dict:
            namespace.vars.update(result)

    def __repr__(self):
        return self.__class__.__name__


class Task(BaseTask):
    pass
