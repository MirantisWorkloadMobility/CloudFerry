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

__author__ = 'mirrorcoder'
import cloudferrylib
import addons
import imp
import os
import inspect
import yaml
from cloudferrylib.base.action import action


class Scenario(object):
    def __init__(self, path_tasks='scenario/tasks.yaml', path_scenario='scenario/migrate.yaml'):
        self.path_tasks = path_tasks
        self.path_scenario = path_scenario

    def init_tasks(self, init={}):
        tasks_file = yaml.load(open(self.path_tasks, 'r'))
        actions = {}
        for mod in tasks_file['paths']:
            actions.update(self.get_actions(mod))
        tasks = {}
        for task in tasks_file['tasks']:
            args = tasks_file['tasks'][task][1:]
            if args and isinstance(args[-1], dict):
                args_map = args[-1]
                args = args[:-1]
            else:
                args_map = {}
            tasks[task] = actions[tasks_file['tasks'][task][0]](init, *args, **args_map)
        self.tasks = tasks

    def load_scenario(self, path_scenario=None):
        if path_scenario is None:
            path_scenario = self.path_scenario
        migrate = yaml.load(open(path_scenario, 'r'))
        self.process = migrate['process']
        self.namespace = migrate['namespace']

    def get_net(self):
        return self.construct_net(self.process, self.tasks)

    def construct_net(self, process, tasks):
        net = None
        for item in process:
            name, value = item.items()[0]
            elem = tasks[name] if name in tasks else None
            if type(value) is type(list()):
                if type(value[0]) is type(dict()):
                    elem = self.construct_net(value, tasks)
                else:
                    for task in value:
                        tasks[name] = tasks[name] | tasks[task]
            if not net and value:
                net = elem
            elif value:
                net = net >> elem
        return net

    def get_actions(self, mod):
        path_split = mod.split(".")
        module = None
        if path_split[0] == 'cloudferrylib':
            module = cloudferrylib
        elif path_split[0] == 'addons':
            module = addons
        for p in path_split[1:]:
            module = module.__dict__[p]
        path = module.__path__[0]
        files = os.listdir(path)
        list_name_modules = filter(lambda x: (".py" in x) and (".pyc" not in x), files)
        list_name_modules = map(lambda x: x.replace(".py", ""), list_name_modules)
        modules = [imp.load_source(name, path+'/%s.py' % name) for name in list_name_modules]
        actions = {}
        for module in modules:
            for item in module.__dict__:
                if inspect.isclass(module.__dict__[item]) and issubclass(module.__dict__[item], action.Action):
                    actions[item] = module.__dict__[item]
        return actions

    def init_process_migrate(self, path):
        migrate = yaml.load(open(path, 'r'))
        process = migrate['process']
        namespace = migrate['namespace']
        return process, namespace