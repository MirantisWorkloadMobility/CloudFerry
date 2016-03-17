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

import warnings
import sys
import traceback

from fabric.api import task, env
import yaml
import oslo_config.cfg
import oslo_config.types

import cfglib
from cloudferrylib import config
from cloudferrylib import stage
from cloudferrylib.os.estimation import procedures
from cloudferrylib.scheduler.namespace import Namespace
from cloudferrylib.scheduler.scheduler import Scheduler
from cloudferrylib.utils import log
from cloudferrylib.utils import utils
from cloudferrylib.utils.errorcodes import ERROR_INVALID_CONFIGURATION
from cloudferrylib.scheduler.scenario import Scenario
from cloud import cloud_ferry
from cloud import grouping
from condensation import process
from condensation import utils as condense_utils
from condensation.action import get_freed_nodes
from condensation.scripts import nova_collector
import data_storage
from dry_run import chain
from evacuation import evacuation_chain
from make_filters import make_filters

env.forward_agent = True
env.user = 'root'
env.cloud = None
env.current_task = None
LOG = log.getLogger(__name__)


DEFAULT_FILTERS_FILES = 'configs/filters'


@task
def migrate(name_config=None, debug=None):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    init(name_config, debug)
    env.key_filename = cfglib.CONF.migrate.key_filename
    env.connection_attempts = cfglib.CONF.migrate.ssh_connection_attempts
    env.cloud = cloud_ferry.CloudFerry(cfglib.CONF)
    status_error = env.cloud.migrate(Scenario(
        path_scenario=cfglib.CONF.migrate.scenario,
        path_tasks=cfglib.CONF.migrate.tasks_mapping))
    sys.exit(status_error)


@task
def get_info(name_config, debug=None):
    init(name_config, debug)
    LOG.info("Init getting information")
    namespace = Namespace({'name_config': name_config})
    Scheduler(namespace)


@task
def dry_run():
    init()
    chain.process_test_chain()


@task
def evacuate(name_config=None, debug=None, iteration=False):
    init(name_config, debug)
    try:
        iteration = int(iteration)
    except ValueError:
        LOG.error("Invalid value provided as 'iteration' argument, it must be "
                  "integer")
        return
    env.key_filename = cfglib.CONF.migrate.key_filename
    cloud = cloud_ferry.CloudFerry(cfglib.CONF)
    LOG.info("running evacuation")
    evacuation_chain.process_chain(cloud, iteration)

    freed_nodes = get_freed_nodes(iteration)

    if not freed_nodes:
        LOG.warning("Evacuation cannot be completed, because there are no "
                    "available compute nodes, that should be freed")
        return

    LOG.info("Following nodes will be freed once in-cloud migration finishes, "
             "and can be moved from source to destination: %s", freed_nodes)


@task
def get_groups(name_config=None, group_file=None, cloud_id='src',
               validate_users_group=False, debug=None):
    """
    Function to group VMs by any of those dependencies (f.e. tenants,
    networks, etc.).

    :param name_config: name of config ini-file, example 'config.ini',
    :param group_file: name of groups defined yaml-file, example 'groups.yaml',
    :param validate_users_group: Remove duplicate IDs and check if valid
           VM id specified. Takes more time because of nova API multiple calls
    :return: yaml-file with tree-based groups defined based on grouping rules.
    """
    init(name_config, debug)
    group = grouping.Grouping(cfglib.CONF, group_file, cloud_id)
    group.group(validate_users_group)


@task
def condense(config=None, vm_grouping_config=None, debug=None):
    """
    When migration is done in-place (there's no spare hardware), cloud
    migration admin would want to free as many hardware nodes as possible. This
    task handles that case by analyzing source cloud and rearranging source
    cloud load and generating migration scenario.

    Condensation is a process of:
     1. Retrieving groups of connected VMs (see `get_groups`)
     2. Rearrangement of source cloud load in order to free up as many
        hardware nodes as possible.
     3. Generation filter files for CloudFerry, which only contain groups of
        VMs identified in step 1 in the order identified in step 2.

    Method arguments:
     :config: - path to CloudFerry configuration file (based on
                `configs/config.ini`)
     :vm_grouping_config: - path to grouping config file (based on
                `configs/groups.yaml`)
     :debug: - boolean value, enables debugging messages if set to `True`
    """
    init(config, debug)
    data_storage.check_redis_config()

    LOG.info("Retrieving flavors, VMs and nodes from SRC cloud")
    flavors, vms, nodes = nova_collector.get_flavors_vms_and_nodes(cfglib.CONF)

    if cfglib.CONF.condense.keep_interim_data:
        condense_utils.store_condense_data(flavors, nodes, vms)

    LOG.info("Retrieving groups of VMs")

    # get_groups stores results in group_file_path config
    get_groups(config, vm_grouping_config)
    groups = condense_utils.read_file(cfglib.CONF.migrate.group_file_path)
    if groups is None:
        message = ("Grouping information is missing. Make sure you have "
                   "grouping file defined in config.")

        LOG.critical(message)
        raise RuntimeError(message)

    LOG.info("Generating migration schedule based on grouping rules")
    process.process(nodes=nodes, flavors=flavors, vms=vms, groups=groups)

    LOG.info("Starting generation of filter files for migration")
    create_filters(config)

    LOG.info("Migration schedule generated. You may now want to start "
             "evacuation job: 'fab evacuate'")

    LOG.info("Condensation process finished. Checkout filters file: %s.",
             DEFAULT_FILTERS_FILES)


@task
def get_condensation_info(name_config=None):
    init(name_config)
    nova_collector.run_it(cfglib.CONF)


@task
def create_filters(name_config=None, filter_folder=DEFAULT_FILTERS_FILES,
                   images_date='2000-01-01'):
    """Generates filter files for CloudFerry based on the schedule prepared by
    condensation/grouping."""
    init(name_config)
    make_filters.make(filter_folder, images_date)


@task
def discover(config_path, debug=False):
    """
        :config_name - name of config yaml-file, example 'config.yaml'
    """
    cfg = config.load(load_yaml_config(config_path, debug))
    stage.execute_stage('cloudferrylib.os.discovery.stages.DiscoverStage', cfg,
                        force=True)


@task
def estimate_migration(config_path, migration, debug=False):
    cfg = config.load(load_yaml_config(config_path, debug))
    if migration not in cfg.migrations:
        print 'No such migration:', migration
        print '\nPlease choose one of this:'
        for name in sorted(cfg.migrations.keys()):
            print '  -', name
        return -1

    stage.execute_stage('cloudferrylib.os.discovery.stages.DiscoverStage', cfg)
    procedures.estimate_copy(cfg, migration)
    procedures.show_largest_servers(cfg, 10, migration)


@task
def show_unused_resources(config_path, cloud, count=100, tenant=None,
                          debug=False):
    cfg = config.load(load_yaml_config(config_path, debug))
    stage.execute_stage('cloudferrylib.os.discovery.stages.DiscoverStage', cfg)
    procedures.show_largest_unused_resources(int(count), cloud, tenant)


def init(name_config=None, debug=None):
    try:
        cfglib.init_config(name_config)
    except oslo_config.cfg.Error:
        traceback.print_exc()
        sys.exit(ERROR_INVALID_CONFIGURATION)

    utils.init_singletones(cfglib.CONF)
    if cfglib.CONF.migrate.hide_ssl_warnings:
        warnings.simplefilter("ignore")
    if debug is not None:
        value = oslo_config.types.Boolean()(debug)
        cfglib.CONF.set_override('debug', value, 'migrate')
    log.configure_logging()


def load_yaml_config(yaml_path, debug=None):
    def import_legacy(cloud, cfg):
        cred = cloud.setdefault('credential', {})
        cred['auth_url'] = cfg.auth_url
        cred['username'] = cfg.user
        cred['password'] = cfg.password
        cred['region_name'] = cfg.region
        cred['https_insecure'] = cfg.insecure
        cred['https_cacert'] = cfg.cacert
        scope = cloud.setdefault('scope', {})
        scope['project_name'] = cfg.tenant
        ssh = cloud.setdefault('ssh', {})
        ssh['gateway'] = cfg.ssh_host
        ssh['username'] = cfg.ssh_user
        ssh['sudo_password'] = cfg.ssh_sudo_password
        ssh['connection_attempts'] = \
            cfglib.CONF.migrate.ssh_connection_attempts

    log.configure_logging(log_config='configs/logging_config.yaml',
                          debug=debug,
                          forward_stdout=False)

    prev_legacy_config_path = None
    with open(yaml_path, 'r') as config_file:
        cfg = yaml.load(config_file)
        clouds = cfg.setdefault('clouds', {})
        for value in clouds.values():
            if 'legacy' not in value:
                continue
            legacy_config_path, section = value.pop('legacy').split(':')
            if prev_legacy_config_path != legacy_config_path:
                init(legacy_config_path, debug)
            import_legacy(value, getattr(cfglib.CONF, section))
        return cfg


if __name__ == '__main__':
    migrate(None)
