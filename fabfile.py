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
from cloud import grouping
from dry_run import chain
from condensation import process
from condensation.scripts import nova_collector as nova_collector_module
env.forward_agent = True
env.user = 'root'
LOG = utl.get_log(__name__)


@task
def migrate(name_config=None, name_instance=None, debug=False):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    if debug:
        utl.configure_logging("DEBUG")
    cfglib.collector_configs_plugins()
    cfglib.init_config(name_config)
    utils.init_singletones(cfglib.CONF)
    env.key_filename = cfglib.CONF.migrate.key_filename
    cloud = cloud_ferry.CloudFerry(cfglib.CONF)
    cloud.migrate(Scenario(path_scenario=cfglib.CONF.migrate.scenario,
                           path_tasks=cfglib.CONF.migrate.tasks_mapping))


@task
def get_info(name_config, debug=False):
    if debug:
        utl.configure_logging("DEBUG")
    LOG.info("Init getting information")
    namespace = Namespace({'name_config': name_config})
    scheduler = Scheduler(namespace)


@task
def dry_run():
    chain.process_test_chain()


@task
def get_groups(name_config=None, group_file=None, cloud_id='src',
               validate_users_group=False):
    """
    Function to group VM's by any of those dependencies (f.e. tenants,
    networks, etc.).

    :param name_config: name of config ini-file, example 'config.ini',
    :param group_file: name of groups defined yaml-file, example 'groups.yaml',
    :param validate_users_group: Remove dublicate id's and check if valid
           VM id specified. Takes more time because of nova API multiple calls
    :return: yaml-file with tree-based groups defined based on grouping rules.
    """
    cfglib.collector_configs_plugins()
    cfglib.init_config(name_config)
    group = grouping.Grouping(cfglib.CONF, group_file, cloud_id)
    group.group(validate_users_group)


@task
def condense(name_config=None, debug=False):
    if debug:
        utl.configure_logging("DEBUG")
    cfglib.collector_configs_plugins()
    cfglib.init_config(name_config)
    process.process()


@task
def nova_collector(name_config=None):
    cfglib.collector_configs_plugins()
    cfglib.init_config(name_config)
    nova_collector_module.run_it(cfglib.CONF)


if __name__ == '__main__':
    migrate(None)
