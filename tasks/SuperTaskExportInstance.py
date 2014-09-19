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

from scheduler.SuperTask import SuperTask
from cloudferrylib.scheduler.task import Task

__author__ = 'mirrorcoder'


class SuperTaskExportInstance(SuperTask):

    def __init__(self, instance=None, namespace=None):
        self.instance = instance
        if not namespace:
            super(SuperTaskExportInstance, self).__init__()
        else:
            super(SuperTaskExportInstance, self).__init__(namespace=namespace)

    def run(self, inst_exporter=None, **kwargs):
        tasks_export = []
        exporter_builder = inst_exporter.export(self.instance)
        tasks = exporter_builder.get_tasks()
        self.namespace.vars['exporter_builder'] = exporter_builder
        tasks_export.extend(tasks)
        tasks_export.append(TaskGetState())
        return tasks_export


class TaskGetState(Task):

    def run(self, exporter_builder=None, **kwargs):
        return {
            'data_export_inst': exporter_builder.get_state()['data']
        }

