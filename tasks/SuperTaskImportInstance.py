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

__author__ = 'mirrorcoder'


class SuperTaskImportInstance(SuperTask):

    def run(self, data_export_inst=None, inst_importer=None, **kwargs):
        tasks_import = []
        importer_builder = inst_importer.upload(data_export_inst)
        self.namespace.vars['import_builder'] = importer_builder
        tasks = importer_builder.get_tasks()
        tasks_import.extend(tasks)
        return tasks_import
