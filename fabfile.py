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

from fabric.api import task, env

from cloudferrylib import config
from cloudferrylib.scheduler.namespace import Namespace
from cloudferrylib.scheduler.scheduler import Scheduler
from utils import get_log

env.forward_agent = True
env.user = 'root'

LOG = get_log(__name__)


@task
def migrate(name_config, name_instance=None):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    config.collector_configs_plugins()
    config.init_config(name_config)
    namespace = Namespace({
        'config': config.CONF,
        'name_instance': name_instance})
    scheduler = Scheduler(namespace)


@task
def get_info(name_config):
    LOG.info("Init getting information")
    namespace = Namespace({'name_config': name_config})
    scheduler = Scheduler(namespace)

if __name__ == '__main__':
    migrate(None)
