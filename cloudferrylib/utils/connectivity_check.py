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

from cloudferrylib.utils import remote_runner


def has_ssh_connectivity(connection_user, user, key, src_host, dst_host):
    """:returns: True if `user@src_host` can ssh into `dst_host` with `key`"""

    rr = remote_runner.RemoteRunner(src_host,
                                    connection_user,
                                    timeout=5)

    try:
        ssh = ("ssh -i {key} "
               "-o StrictHostKeyChecking=no "
               "-o UserKnownHostsFile=/dev/null "
               "{user}@{dst_host} 'echo'")
        rr.run(ssh.format(key=key, user=user, dst_host=dst_host))
        return True
    except remote_runner.RemoteExecutionError:
        return False
