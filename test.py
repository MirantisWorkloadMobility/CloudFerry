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

from scheduler.Scheduler import *
from scheduler.ThreadTasks import *
from scheduler.ExampleTasks import *

def get_id_action(prefix='a%s', count={'c': 1}):
    j = count

    def f():
        r = prefix % j['c']
        j['c'] += 1
        return r
    return f

f = get_id_action()
a1, a2, a3, a4, a5, a6, a7, a8 = Action(f()), Action(f()), Action(f()), Action(f()), Action(f()), Action(f()), Action(f()), Action(f())
for a in (a1, a2, a3, a4, a5, a6):
    print "id=%s" % id(a)
d = {'c': 1}
f1 = get_id_action(prefix='a1%s', count=d)
f2 = get_id_action(prefix='a2%s', count=d)
a11, a12, a13, a24, a25, a26 = ThreadAction(f1()), ThreadAction(f1()), ThreadAction(f1()), ThreadAction(f2()), ThreadAction(f2()), ThreadAction(f2())
for a in (a11, a12, a13, a24, a25, a26):
    print "id=%s" % id(a)
tt1 = WrapThreadTask(a11 >> a12 >> a13, NORMAL)
tt2 = WrapThreadTask(a24 >> a25 >> a26, NORMAL)
res = a1 >> a2 >> (a3 & tt1 & tt2) >> WaitThreadAllTask() >> a4 >> (a5 | (a6 - a7) | (a8 - a7)) >> a7
cursor = Cursor(res)
namespace = Namespace()
scheduler = Scheduler(namespace, cursor=cursor)
scheduler.start()
