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

import yaml
from fabric.api import task, env
from scheduler.Namespace import Namespace
from scheduler.Scheduler import Scheduler
from tasks.SuperTaskImportResource import SuperTaskImportResource
from tasks.TaskInitMigrate import TaskInitMigrate
from tasks.SuperTaskExportResource import SuperTaskExportResource
from tasks.SuperTaskMigrateInstances import SuperTaskMigrateInstances

from utils import log_step, get_log

env.forward_agent = True
env.user = 'root'

LOG = get_log(__name__)


@task
def migrate(name_config, name_instance=None):
    """
        :name_config - name of config yaml-file, example 'config.yaml'
    """
    namespace = Namespace({'name_config': name_config,
                           'name_instance': name_instance})
    scheduler = Scheduler(namespace)
    scheduler.addTask(TaskInitMigrate())
    scheduler.addTask(SuperTaskExportResource())
    scheduler.addTask(SuperTaskImportResource())
    scheduler.addTask(SuperTaskMigrateInstances())
    scheduler.run()

@task
def clean_dest_cloud(name_config, delete_image=False):
    LOG.info("Init config migrate")
    # _, (_, _), (_, importer) = init_migrate(name_config)
    # importer.clean_cloud(delete_image)
