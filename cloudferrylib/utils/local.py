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

from fabric import api

LOG = logging.getLogger(__name__)


class LocalExecutionFailed(RuntimeError):
    def __init__(self, msg, code):
        super(LocalExecutionFailed, self).__init__()
        self.code = code
        self.message = msg


def run(cmd, capture_output=True):
    """
    Run command locally with current user privileges
    :returns: command output on success
    :raises: LocalExecutionFailed if command failed"""
    try:
        LOG.debug("Running '%s' locally", cmd)
        return api.local(cmd, capture=capture_output)
    except SystemExit as e:
        LOG.debug("Command '%s' failed with '%s'", cmd, e.message)
        raise LocalExecutionFailed(e.message, e.code)


def sudo(cmd, sudo_password=None, capture_output=True):
    if sudo_password:
        # make sure back slashes and quotation marks are handled correctly
        pwd = sudo_password.replace("\\", "\\\\").replace("'", "'\\''")
        # TODO logs password in plaintext (!!!)
        sudo_cmd = "echo '{passwd}' | sudo -S {cmd}".format(passwd=pwd,
                                                            cmd=cmd)
    else:
        sudo_cmd = "sudo {cmd}".format(cmd=cmd)
    return run(sudo_cmd, capture_output=capture_output)


def run_ignoring_errors(cmd):
    """Suppresses all command execution errors
    :returns: (retcode, output) pair
    """
    try:
        output = run(cmd, capture_output=True)
        return 0, output
    except LocalExecutionFailed as e:
        return e.code, e.message


def sudo_ignoring_errors(cmd, sudo_password=None):
    """Suppresses all command execution errors
    :returns: (retcode, output) pair
    """
    try:
        output = sudo(cmd, capture_output=True, sudo_password=sudo_password)
        return 0, output
    except LocalExecutionFailed as e:
        return e.code, e.message
