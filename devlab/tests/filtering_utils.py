# Copyright (c) 2015 Mirantis Inc.
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

import os
import yaml
import config


class FilteringUtils(object):
    def __init__(self):
        # TODO:
        #  Using relative paths is a bad practice, unfortunately this is the
        #  only way at this moment.
        #  Should be fixed by implementing proper package module for
        #  Cloud Ferry.
        self.main_folder = os.path.dirname(os.path.dirname(os.getcwd()))

    def load_file(self, file_name):
        file_path = os.path.join(self.main_folder, file_name.lstrip('/'))
        with open(file_path, "r") as f:
            filter_dict = yaml.load(f)
        return [filter_dict, file_path]

    def filter_vms(self, src_data_list):
        loaded_data = self.load_file('configs/filter.yaml')
        filter_dict = loaded_data[0]
        popped_vm_list = []
        if 'instances' not in filter_dict:
            return [src_data_list, []]
        for vm in src_data_list[:]:
            if vm['id'] not in filter_dict['instances']['id']:
                popped_vm_list.append(vm)
                index = src_data_list.index(vm)
                src_data_list.pop(index)
        return [src_data_list, popped_vm_list]

    def filter_images(self, src_data_list):
        loaded_data = self.load_file('configs/filter.yaml')
        filter_dict = loaded_data[0]
        popped_img_list = []
        default_img = 'Cirros 0.3.0 x86_64'
        src_data_list = [x.__dict__ for x in src_data_list]
        if 'images' not in filter_dict:
            return [src_data_list, []]
        for img in src_data_list[:]:
            if img['id'] not in filter_dict['images']['images_list']:
                if img['name'] != default_img:
                    popped_img_list.append(img)
                    index = src_data_list.index(img)
                    src_data_list.pop(index)
        return [src_data_list, popped_img_list]

    def get_resource_names(self, obj, cfg):
        if obj == 'routers':
            return [i['router']['name'] for i in cfg]
        else:
            return [i['name'] for i in cfg]

    def get_resources_from_config(self, res):
        if res == 'security_groups':
            return [sg for i in config.tenants if 'security_groups' in i
                    for sg in i['security_groups']]
        elif res == 'servers':
            cfg = getattr(config, 'vms')
            [cfg.extend(i['vms']) for i in config.tenants if 'vms' in i]
            return cfg
        elif res == 'volumes':
            res = 'cinder_volumes'

        return getattr(config, res)
