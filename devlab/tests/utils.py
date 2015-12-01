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
import ConfigParser

from fabric.api import run, settings, sudo, hide
from fabric.network import NetworkError


class FilteringUtils(object):

    def __init__(self):
        self.main_folder = os.path.dirname(os.path.dirname(
            os.path.split(__file__)[0]))
        cf_config = ConfigParser.ConfigParser()
        cf_config.read(os.path.join(self.main_folder,
                                    config.cloud_ferry_conf))
        self.filter_file_path = cf_config.get('migrate', 'filter_path')
        self.filters_file_naming_template = config.filters_file_naming_template

    def build_filter_files_list(self):
        return [self.filters_file_naming_template.format(
            tenant_name=tenant['name'])
            for tenant in config.tenants
            if 'deleted' not in tenant and not tenant['deleted']]

    def load_file(self, file_name):
        file_path = os.path.join(self.main_folder, file_name.lstrip('/'))
        with open(file_path, "r") as f:
            filter_dict = yaml.load(f)
        return [filter_dict, file_path]

    def filter_vms(self, src_data_list):
        loaded_data = self.load_file(self.filter_file_path)
        filter_dict = loaded_data[0]
        popped_vm_list = []
        if 'instances' not in filter_dict:
            return [src_data_list, []]
        for vm in src_data_list[:]:
            if vm.id not in filter_dict['instances']['id']:
                popped_vm_list.append(vm)
                index = src_data_list.index(vm)
                src_data_list.pop(index)
        return [src_data_list, popped_vm_list]

    def filter_images(self, src_data_list):
        loaded_data = self.load_file(self.filter_file_path)
        filter_dict = loaded_data[0]
        popped_img_list = []
        default_img = 'Cirros 0.3.0 x86_64'
        if 'images' not in filter_dict:
            return [src_data_list, []]
        for img in src_data_list[:]:
            if img.id not in filter_dict['images']['images_list']:
                if img.name != default_img:
                    popped_img_list.append(img)
                    index = src_data_list.index(img)
                    src_data_list.pop(index)
        return [src_data_list, popped_img_list]

    def filter_tenants(self, src_data_list):
        loaded_data = self.load_file(self.filter_file_path)
        filter_dict = loaded_data[0]
        popped_tenant_list = []
        if 'tenants' not in filter_dict:
            return [src_data_list, []]
        for tenant in src_data_list:
            if tenant.id not in filter_dict['tenants']['tenant_id']:
                popped_tenant_list.append(tenant)
                index = src_data_list.index(tenant)
                src_data_list.pop(index)
        return [src_data_list, popped_tenant_list]

    @staticmethod
    def get_vm_fip(vm):
        for net in vm.addresses:
            for addr in vm.addresses[net]:
                if addr['OS-EXT-IPS:type'] == 'floating':
                    return addr['addr']
        raise RuntimeError('VM with name {} and id {} doesnt have fip'.format(
            vm.name, vm.id))


class MigrationUtils(object):

    def __init__(self, config):
        self.config = config

    def execute_command_on_vm(self, ip_addr, cmd, username=None,
                              warn_only=False, password=None, key=None,
                              use_sudo=True):

        if username is None:
            username = self.config.username_for_ssh
        if password is None and key is None:
            password = self.config.password_for_ssh
        with hide('everything'), settings(
                host_string=ip_addr, user=username, password=password, key=key,
                abort_on_prompts=True, connection_attempts=3,
                disable_known_hosts=True, no_agent=True, warn_only=warn_only):
            try:
                if use_sudo:
                    return sudo(cmd, shell=False)
                else:
                    return run(cmd, shell=False)
            except NetworkError:
                raise RuntimeError('VM with name ip: %s is not accessible'
                                   % ip_addr)

    def get_all_vms_from_config(self):
        vms = self.config.vms
        for tenant in self.config.tenants:
            if not tenant.get('vms'):
                continue
            for vm in tenant['vms']:
                vms.append(vm)
        vms.extend(self.config.vms_from_volumes)
        return vms

    def get_all_images_from_config(self):
        images = self.config.images
        for tenant in self.config.tenants:
            if not tenant.get('images'):
                continue
            for image in tenant['images']:
                images.append(image)
        return images
