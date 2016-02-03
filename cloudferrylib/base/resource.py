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

from cloudferrylib.base import exception
from cloudferrylib.utils import log
from cloudferrylib.utils import proxy_client

LOG = log.getLogger(__name__)


class Resource(object):
    def __init__(self):
        pass

    def proxy(self, client, cfg):
        retry = cfg.migrate.retry
        time_wait = cfg.migrate.time_wait
        return proxy_client.Proxy(client, retry, time_wait)

    def read_info(self, opts=None):
        pass

    def deploy(self, *args, **kwargs):
        pass

    def save(self):
        pass

    def restore(self):
        pass

    def required_tenants(
            self,
            filter_tenant_id=None):  # pylint: disable=unused-argument
        """Returns list of tenants required by resource. Important for the
        filtering feature."""
        return []

    def wait_for_status(self, res_id, get_status, wait_status, timeout=60,
                        stop_statuses=None):
        LOG.debug("Waiting for status change")
        delay = 1
        stop_statuses = [s.lower() for s in (stop_statuses or [])]
        if 'error' not in stop_statuses:
            stop_statuses.append('error')
        while delay < timeout:
            actual_status = get_status(res_id).lower()
            LOG.debug("Expected status is '%s', actual - '%s', "
                      "stop statuses - %s",
                      wait_status, actual_status, stop_statuses)
            if actual_status in stop_statuses:
                LOG.debug("Stop status reached, exit")
                raise exception.TimeoutException(
                    get_status(res_id).lower(),
                    wait_status, "Timed out waiting for state change")
            elif actual_status == wait_status.lower():
                LOG.debug("Expected status reached, exit")
                break

            LOG.debug("Expected status NOT reached, waiting")

            time.sleep(delay)
            delay *= 2
        else:
            LOG.debug("Timed out waiting for state change")
            raise exception.TimeoutException(
                get_status(res_id).lower(),
                wait_status, "Timed out waiting for state change")

    def try_wait_for_status(self, res_id, get_status, wait_status, timeout=60):
        try:
            self.wait_for_status(res_id, get_status, wait_status, timeout)
        except exception.TimeoutException as e:
            LOG.warning("Resource '%s' has not changed status to '%s'(%s)",
                        res_id, wait_status, e)

    def get_status(self, resource_id):
        pass

    def __deepcopy__(self, memo):
        return self
