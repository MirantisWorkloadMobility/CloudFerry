# Copyright (c) 2016 Mirantis Inc.
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

import os
import time

import cfglib
from cloudferrylib.utils import log
from cloudferrylib.utils import sizeof_format

LOG = log.getLogger(__name__)
CONF = cfglib.CONF


def get_file_size(file_obj):
    """
    Analyze file-like object and attempt to determine its size.

    :param file_obj: file-like object.
    :retval The file's size or None if it cannot be determined.
    """
    if hasattr(file_obj, 'seek') and hasattr(file_obj, 'tell'):
        try:
            curr = file_obj.tell()
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            file_obj.seek(curr)
            return size
        except IOError:
            return


class ProgressView(object):
    def __init__(self, name=None, size=None):
        self.name = name
        self.size = size
        self.size_hr = sizeof_format.sizeof_fmt(size) if size else "NAN"
        self.show_size = (size / 100 if size else
                          sizeof_format.parse_size('100MB'))
        self.current_show_size = 0
        self.progress_message = "Copying %(name)s: %(progress)s of %(size)s"
        if size:
            self.progress_message += " %(percentage)s%%"
        self.progress = 0
        self.first_run = None

    def inc_progress(self, value):
        self.progress += value

    def show_progress(self):
        progress_hr = sizeof_format.sizeof_fmt(self.progress)
        args = {'progress': progress_hr,
                'size': self.size_hr,
                'name': self.name}
        if self.size:
            args['percentage'] = self.progress * 100 / self.size

        LOG.info(self.progress_message, args)

    def __call__(self, value):
        if self.first_run is None:
            self.first_run = time.time()
        self.inc_progress(value)
        self.current_show_size += value
        if (self.current_show_size >= self.show_size and
                self.first_run + 5 < time.time()):
            self.current_show_size = 0
            self.show_progress()


class SpeedLimiter(object):
    def __init__(self, speed_limit=None):
        self.speed_limit = sizeof_format.parse_size(speed_limit)
        self.prev_time = None
        self.sent_size = 0

    def __call__(self, size):
        if not self.speed_limit:
            return

        if self.prev_time is None:
            self.prev_time = time.time()
        else:
            sleep_time = float(self.sent_size) / self.speed_limit
            sleep_time -= time.time() - self.prev_time
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.sent_size = 0
                self.prev_time = time.time()
        self.sent_size += size


class FileProxy(object):
    def __init__(self, file_obj, speed_limit=None, size=None, name=None,
                 chunk_size='512K'):
        self.file_obj = file_obj
        self.chunk_size = sizeof_format.parse_size(chunk_size)
        self.speed_limiter = SpeedLimiter(speed_limit or
                                          CONF.migrate.speed_limit)
        if size is None:
            size = get_file_size(file_obj)
        name = name or getattr(file_obj, 'name', '<file object>')
        self.view = ProgressView(name=name, size=size)

    def read(self, size=None):
        size = size or self.chunk_size
        data = self.file_obj.read(size)
        length_data = len(data)
        self.view(length_data)
        self.speed_limiter(length_data)

        return data

    def __getattr__(self, item):
        if item == 'seek':
            raise AttributeError()
        return getattr(self.file_obj, item)
