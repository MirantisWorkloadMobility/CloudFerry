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

CONTINUE = "continue"
ABORT = "abort"
SKIP = "skip"
RESTART = "restart"


class Rollback(object):
    def __call__(self, __rollback_status__=RESTART, *args, **kwargs):
        return {
            CONTINUE: self.continue_status,
            ABORT: self.abort_status,
            SKIP: self.skip_status,
            RESTART: self.restart_status
        }[__rollback_status__](*args, **kwargs)

    def continue_status(self, *args, **kwargs):
        return True

    def abort_status(self, *args, **kwargs):
        return True

    def skip_status(self, *args, **kwargs):
        return True

    def restart_status(self, *args, **kwargs):
        return True
