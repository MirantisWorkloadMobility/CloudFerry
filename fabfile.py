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
from cloudferrylib.scheduler.namespace import Namespace
from cloudferrylib.scheduler.scheduler import Scheduler
import cfglib
from cloudferrylib.utils import utils as utl
from cloudferrylib.utils import utils
from cloudferrylib.scheduler.scenario import Scenario
from cloud import cloud_ferry
from dry_run import chain
env.forward_agent = True
env.user = 'root'
LOG = utl.get_log(__name__)


@task
def migrate(name_config=None, name_instance=None):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    cfglib.collector_configs_plugins()
    cfglib.init_config(name_config)
    utils.init_singletones(cfglib.CONF)
    env.key_filename = cfglib.CONF.migrate.key_filename
    cloud = cloud_ferry.CloudFerry(cfglib.CONF)
    cloud.migrate(Scenario())


@task
def get_info(name_config):
    LOG.info("Init getting information")
    namespace = Namespace({'name_config': name_config})
    scheduler = Scheduler(namespace)


@task
def dry_run():
    chain.process_test_chain()


if __name__ == '__main__':
    migrate(None)
