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

HIGH = 3
NORMAL = 2
LOW = 1

DEFAULT = 0
NO_ELEMENT = 0


class EquInstance(object):
    def __hash__(self):
        return hash(self.__class__.__name__)

    def __eq__(self, other):
        return hash(self) == hash(other)


class ThreadTask(object):
    def __init__(self, net=None, priority=None):
        self.net = net
        self.priority = priority

    def getNet(self):
        return self.net


class Element:
    def __init__(self):
        self.prev_element = None
        self.next_element = []
        self.num_element = DEFAULT

    def next(self):
        element = self.next_element[self.num_element] if self.next_element else NO_ELEMENT
        if element == NO_ELEMENT:
            raise StopIteration
        return element

    def __iter__(self):
        return self

    def toStart(self):
        obj = self
        while obj.prev_element:
            obj = obj.prev_element
        return obj


class AltSyntax(Element):
    def __sub__(self, other):
        self.next_element.append(other)
        return self

    def __or__(self, other):
        other = other.toStart()
        self.next_element.append(other)
        other.prev_element = self
        return self

    def __and__(self, other):
        self.next_element.append(other)
        return self

    def __rshift__(self, other):
        self.next_element.insert(0, other)
        other.prev_element = self if not other.prev_element else other.prev_element
        return other


class ClassicSyntax(Element):
    def oneWayLink(self, other):
        self.next_element.append(other)
        return self

    def anotherWay(self, other):
        other = other.toStart()
        self.next_element.append(other)
        other.prev_element = self
        return self

    def addThread(self, other):
        self.next_element.append(other)
        return self

    def dualWayLink(self, other):
        self.next_element.insert(0, other)
        other.prev_element = self if not other.prev_element else other.prev_element
        return other


class Task(EquInstance, AltSyntax):
    def run(self):
        pass

    def __call__(self, namespace=None):
        result, num_task = self.run(**namespace.vars)
        namespace.vars.update(result)
        self.num_element = num_task if num_task else DEFAULT

    def __repr__(self):
        return "Task|%s" % self.__class__.__name__


class WaitThreadTask(Task):
    def __init__(self, tt):
        self.tt = tt
        super(WaitThreadTask, self).__init__()

    def run(self):
        pass


class WaitThreadAllTask(Task):
    def run(self):
        pass


class Action(Task):
    pass