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

from scheduler.Task import Task
from utils import get_log, PATH_TO_SNAPSHOTS
import shutil
import yaml
import os

__author__ = 'mirrorcoder'

LOG = get_log(__name__)


class TaskInitDirectory(Task):

    def run(self, **kwargs):
        LOG.info("Init directory")
        if os.path.exists("transaction"):
            shutil.rmtree("transaction")
        if os.path.exists(PATH_TO_SNAPSHOTS):
            shutil.rmtree(PATH_TO_SNAPSHOTS)
        return {
        }
