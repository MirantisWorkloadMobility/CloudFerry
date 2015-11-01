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


import progressbar
import re
import time

from utils import get_log

LOG = get_log(__name__)

# Maximum Bytes Per Packet
CHUNK_SIZE = 512 * 1024  # B


class FileLikeProxy:
    def __init__(self, transfer_object, callback, speed_limit='1mb'):
        self.__callback = callback if callback \
            else lambda size, length, obj_id, name: True
        self.resp = transfer_object['resource'].get_ref_image(
            transfer_object['id'])
        self.length = (
            self.resp.length if self.resp.length else transfer_object['size'])
        self.id = transfer_object['id']
        self.name = transfer_object['name']
        self.percent = self.length / 100
        self.res = 0
        self.delta = 0
        self.buffer = ''
        self.prev_send_time = 0
        self.speed_limit = self._parse_speed_limit(speed_limit)
        if self.speed_limit != 0:
            self.read = self.speed_limited_read
        msg = 'Download file {}({}): '.format(self.name, self.id)
        self.bar = progressbar.ProgressBar(
            widgets=[
                msg,
                progressbar.Bar(left='[',
                                marker='=',
                                right=']'),
                progressbar.Percentage()
            ]
        ).start()

    def _parse_speed_limit(self, speed_limit):
        if speed_limit is '-':
            return 0
        array = filter(None, re.split(r'(\d+)', speed_limit))
        mult = {
            'b': 1,
            'kb': 1024,
            'mb': 1024 * 1024,
        }[array[1].lower()]
        return int(array[0]) * mult

    def read(self, *args, **kwargs):
        res = self.resp.read(*args, **kwargs)
        self._trigger_callback(len(res))
        return res

    def speed_limited_read(self, *args, **kwargs):
        if len(self.buffer) < CHUNK_SIZE:
            self.buffer += self.resp.read(*args, **kwargs)

        res = self.buffer[0:CHUNK_SIZE]
        self.buffer = self.buffer[CHUNK_SIZE::]

        self._trigger_callback(len(res))

        # avoid division by zero
        if self.speed_limit > 0:
            cur_send_time = time.time()
            sleep_time = float(len(res)) / self.speed_limit
            sleep_time -= cur_send_time - self.prev_send_time
            time.sleep(max(0, sleep_time))
            self.prev_send_time = cur_send_time
        return res

    def _trigger_callback(self, len_data):
        self.delta += len_data
        self.res += len_data
        if (self.delta > self.percent or len_data == 0) and self.length > 0:
            self.bar.update(self.res * 100 / self.length)
            self.delta = 0
        if len_data == 0:
            self.bar.finish()

    def close(self):
        self.resp.close()

    def isclosed(self):
        return self.resp.isclosed()

    def begin(self):
        return self.resp.begin()

    def getheader(self, *args, **kwargs):
        res = self.resp.getheader(*args, **kwargs)
        return res
