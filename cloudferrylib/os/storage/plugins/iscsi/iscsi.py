# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import re

from cloudferrylib.utils import local
from cloudferrylib.utils import retrying

LOG = logging.getLogger(__name__)


class CannotConnectISCSIVolume(RuntimeError):
    pass


def get_device_path(target_portal, target_iqn, target_lun):
    path = "/dev/disk/by-path/ip-{portal}-iscsi-{iqn}-lun-{lun}"
    return path.format(portal=target_portal,
                       iqn=target_iqn,
                       lun=target_lun)


def get_name_from_path(path):
    """Translates /dev/disk/by-path/ entry to /dev/sdX."""
    name = os.path.realpath(path)
    if name.startswith("/dev/"):
        return name
    else:
        return None


def flush_device_io(device):
    local.sudo('blockdev --flushbufs {device}'.format(device=device))


def remove_iscsi_device(dev_name):
    path = "/sys/block/%s/device/delete" % dev_name.replace("/dev/", "")

    if os.path.exists(path):
        flush_device_io(dev_name)
        local.run("echo 1 | sudo tee -a {path}".format(path=path))


def rescan_iscsi():
    local.sudo('iscsiadm -m node --rescan')
    local.sudo('iscsiadm -m session --rescan')


class ISCSIConnector(object):
    def __init__(self, num_retries=1,
                 local_sudo_password=None,
                 storage_backend_timeout=100):
        if num_retries <= 0:
            num_retries = 1
        self.max_attempts = num_retries
        self.sudo_password = local_sudo_password
        self.storage_backend_timeout = storage_backend_timeout

    def _path_exists(self, path, target_portal, target_iqn):
        timeout = self.storage_backend_timeout
        retryer = retrying.retry(max_time=timeout, raise_error=False)

        def check_path_and_rescan():
            # The rescan isn't documented as being necessary(?), but it helps
            try:
                rescan = "iscsiadm -m node -T {iqn} -p {portal} --rescan"
                local.sudo(rescan.format(iqn=target_iqn, portal=target_portal))
            except local.LocalExecutionFailed as e:
                LOG.debug("Rescan failed with %d: %s", e.code, e.message)
            return local.sudo("test -e {path}".format(path=path))

        return retryer.run(check_path_and_rescan) == ''

    def get_sessions(self):
        password = self.sudo_password
        _, out = local.sudo_ignoring_errors('iscsiadm -m session',
                                            sudo_password=password)

        sessions = [VolumeParams.from_iscsiadm_string(l)
                    for l in out.splitlines()]

        return [s for s in sessions if s is not None]

    def connect_volume(self, target_portal, target_iqn, target_lun):
        """:raises: CannotConnectISCSIVolume if volume is not available or
        cannot be connected"""
        connect_cmd = ('iscsiadm '
                       '-m node '
                       '-T {target_iqn} '
                       '-p {target_portal}').format(
            target_iqn=target_iqn, target_portal=target_portal)

        password = self.sudo_password
        local.sudo_ignoring_errors(connect_cmd, sudo_password=password)

        sessions = self.get_sessions()

        if len(sessions) == 0 or not any((s.target_portal == target_portal
                                          for s in sessions)):
            try:
                local.sudo(connect_cmd + ' --login', sudo_password=password)
            finally:
                update = ' --op update -n node.startup -v automatic'
                local.sudo_ignoring_errors(connect_cmd + update)
        device_path = get_device_path(target_portal, target_iqn, target_lun)

        if not self._path_exists(device_path, target_portal, target_iqn):
            msg = "iSCSI volume not found at {host_device}".format(
                host_device=device_path)
            LOG.error(msg)
            raise CannotConnectISCSIVolume(msg)
        return device_path

    def disconnect_volume(self, target_portal, target_iqn, target_lun):
        try:
            rescan_iscsi()
        except local.LocalExecutionFailed as e:
            LOG.warning("Rescanning iSCSI failed with %s", e.message)
        host_device = get_device_path(target_portal, target_iqn, target_lun)
        dev_name = get_name_from_path(host_device)
        if dev_name:
            remove_iscsi_device(dev_name)

    def discover(self, portal):
        discover = 'iscsiadm -m discovery -t sendtargets -p {portal}'

        discovered = local.sudo(
            discover.format(portal=portal),
            sudo_password=self.sudo_password)

        if discovered:
            return [VolumeParams.from_iscsiadm_string(s)
                    for s in discovered.splitlines()]


class VolumeParams(object):
    def __init__(self, portal, iqn, lun):
        self.target_portal = portal
        self.target_iqn = iqn
        self.target_lun = lun

    @classmethod
    def from_iscsiadm_string(cls, iscsiadm_string):
        pattern = r'^.*?([.0-9]+:\d+),(\d+) ([-.:a-zA-Z0-9]+)$'
        matched = re.match(pattern, iscsiadm_string)

        if not matched:
            return None

        portal = matched.group(1)
        lun = int(matched.group(2))
        iqn = matched.group(3)

        return cls(portal=portal, iqn=iqn, lun=lun)

    def __repr__(self):
        s = "VolumeParams<{portal}, {iqn}, {lun}>"
        return s.format(portal=self.target_portal,
                        iqn=self.target_iqn,
                        lun=self.target_lun)
