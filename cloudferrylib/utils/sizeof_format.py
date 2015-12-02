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

UNITS = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']


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
