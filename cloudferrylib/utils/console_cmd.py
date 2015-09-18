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


class BC(object):
    def __init__(self, command):
        self.command = command

    def __add__(self, other):
        return BC(self.command + "; " + other.command)

    def __rshift__(self, other):
        return BC(self.command + " | " + other.command)

    def __and__(self, other):
        return BC(self.command + " && " + other.command)

    def __call__(self, *args):
        return BC(str(self) % args)

    def __str__(self):
        return self.command
