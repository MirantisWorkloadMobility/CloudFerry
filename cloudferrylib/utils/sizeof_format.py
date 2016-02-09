# Copyright (c) 2015 Mirantis Inc.
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

import re

UNITS = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']
RE_SIZE = re.compile(r'(?P<number>\d+)(?P<unit>.*)')
TIME_UNITS = [(29030400, ('year', 'years')),
              (2419200, ('month', 'months')),
              (604800, ('week', 'weeks')),
              (86400, ('day', 'days')),
              (3600, ('hour', 'hours')),
              (60, ('minute', 'minutes')),
              (1, ('second', 'seconds'))]


def sizeof_fmt(num, unit='', suffix='B'):
    """ Format the number to get the human readable version.

    :param num: Number
    :param unit: Current unit of the number
    :param suffix: Suffix of the result
    :return: String with human readable version of the number
    """

    for unit in UNITS[UNITS.index(unit.upper()):]:
        if abs(num) < 1024.:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.
    return "%.1f%s%s" % (num, 'Y', suffix)


def parse_size(size):
    if isinstance(size, (int, long)):
        return max((0, size))
    if isinstance(size, basestring):
        size = size.upper()
        if size == 'OFF':
            return 0
        else:
            m = RE_SIZE.match(size)
            if m:
                try:
                    p = UNITS.index(m.group('unit')[:1])
                except ValueError:
                    p = 0
                return (int(m.group('number')) * 1024 ** p)
    return 0


def timedelta_fmt(seconds):
    result = []

    seconds = int(seconds)
    for interval, name in TIME_UNITS:
        amount = seconds / interval
        if amount > 0:
            result.append('{0} {1}'.format(amount, name[1 % amount]))
            seconds -= amount * interval
    return ', '.join(result)
