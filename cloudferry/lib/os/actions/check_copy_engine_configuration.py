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

import logging
import os

from cloudferry.lib.base.action import action
from cloudferry.lib.base import exception

LOG = logging.getLogger(__name__)


class CheckCopyEngineConfiguration(action.Action):
    def run(self, **kwargs):
        copy_backend = self.cfg.migrate.copy_backend
        if copy_backend == 'bbcp':
            self.check_bbcp()
        elif copy_backend == 'rsync':
            self.check_rsync()

    def check_bbcp(self):
        msg = "Invalid path '{path}' specified in [bbcp] {name} config option"
        messages = []
        for name in ('path', 'src_path', 'dst_path'):
            path = self.cfg.bbcp.get(name)
            if not os.path.isfile(path):
                messages.append(msg.format(path=path, name=name))
        if messages:
            raise exception.InvalidConfigException('\n'.join(messages))

    def check_rsync(self):
        if not self.cfg.migrate.direct_transfer:
            port = self.cfg.rsync.port
            self.cfg.clear_override('port', 'rsync')
            if port == self.cfg.rsync.port:
                LOG.warning('The port option of rsync section has the default '
                            'value. In case of parallel execution on same '
                            'controller the ports must be different.')
            self.cfg.set_override('port', port, 'rsync')
