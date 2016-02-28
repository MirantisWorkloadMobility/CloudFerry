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


class CFBaseException(RuntimeError):
    message = ''

    def __init__(self, message=None, **kwargs):
        message = message or self.message
        super(CFBaseException, self).__init__(message.format(**kwargs))


class OutOfResources(CFBaseException):
    pass


class ImageDownloadError(CFBaseException):
    pass


class AbortMigrationError(CFBaseException):
    """Non-recoverable exception which must be used in cases where migration
    process MUST be aborted"""
    pass


class TimeoutException(RuntimeError):
    def __init__(self, status_obj, exp_status, msg):
        self.status_obj = status_obj
        self.exp_status = exp_status
        self.msg = msg
        super(TimeoutException, self).__init__()


class InvalidConfigException(AbortMigrationError):
    pass


class TenantNotPresentInDestination(RuntimeError):
    pass
