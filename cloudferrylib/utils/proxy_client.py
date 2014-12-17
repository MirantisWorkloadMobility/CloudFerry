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
import time
import inspect
__author__ = 'mirrorcoder'


class Proxy:
    def __init__(self, client, retry, wait_time):
        self.client = client
        self.retry = retry
        self.wait_time = wait_time

    def wait(self):
        time.sleep(self.wait_time)

    def __getattr__(self, name):
        attr = getattr(self.client, name)

        def wrapper(*args, **kwargs):
            c = 0
            result = None
            is_retry = True
            while is_retry:
                try:
                    result = attr(*args, **kwargs)
                    is_retry = False
                except Exception as e:
                    if c < self.retry:
                        c += 1
                        self.wait()
                    else:
                        raise e
            return result
        if inspect.ismethod(attr):
            return wrapper
        elif '__class__' in dir(attr):
            return Proxy(attr, self.retry, self.wait_time)
        return attr
