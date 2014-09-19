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


import time

from novaclient.v1_1 import client as nova_client

from cloudferrylib.base import Compute
from utils.utils import get_libvirt_block_info


DISK = "disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36


class NovaCompute(Compute.Compute):
    """The main class for working with Openstack Nova Compute Service. """

    def __init__(self, config):
        self.config = config
        self.nova_client = self.get_nova_client(self.config)
        self.instance = None
        super(NovaCompute, self).__init__()

    def get_nova_client(self, params):
        """Getting nova client. """

        return nova_client.Client(params["user"],
                                  params["password"],
                                  params["tenant"],
                                  "http://%s:35357/v2.0/" % params["host"])

    def create_instance(self, **kwargs):
        self.instance = self.nova_client.servers.create(**kwargs)
        return self.instance.id

    def get_instances_list(self, detailed=True, search_opts=None, marker=None,
                           limit=None):
        return self.nova_client.servers.list(detailed=detailed,
                                             search_opts=search_opts,
                                             marker=marker, limit=limit)

    def change_status(self, status, instance=None):
        instance = instance if instance else self.instance
        status_map = {
            'start': lambda instance: instance.start(),
            'stop': lambda instance: instance.stop(),
            'resume': lambda instance: instance.resume(),
            'paused': lambda instance: instance.pause(),
            'unpaused': lambda instance: instance.unpause(),
            'suspend': lambda instance: instance.suspend()
        }
        if self.get_status(self.nova_client.servers,
                           instance.id).lower() != status:
            status_map[status](instance)

    def get_instance_info_by_id(self, instance_id):
        # FIXME(toha) This code should be cleaned up and covered by unit tests
        instance = self.nova_client.servers.get(instance_id)
        instance_info = dict()
        attributes = ['id', 'name', 'metadata', 'OS-EXT-AZ:availability_zone', 'config_drive', 'OS-DCF:diskConfig',
                      'OS-EXT-SRV-ATTR:instance_name', 'security_groups', 'key_name', 'addresses',
                      'OS-EXT-SRV-ATTR:host', 'flavor']
        for attribut in attributes:
            instance_info[attribut] = getattr(instance, attribut) if hasattr(instance, attribut) else None
        instance_blkinfo = get_libvirt_block_info(instance_info['OS-EXT-SRV-ATTR:instance_name'], self.config['host'],
                                                  instance_info['OS-EXT-SRV-ATTR:host'])
        instance_info['root_disk_path'] = self.__get_disk_path(DISK, instance_blkinfo, instance_info,
                                                               self.config['ephemeral_drives']['ceph'])
        if (instance_info['root_disk_path'] + LOCAL) in instance_blkinfo:
            instance_info['ephem_disk_path'] = instance_info['root_disk_path'] + LOCAL
        else:
            instance_info['ephem_disk_path'] = None
        return instance_info

    def __get_disk_path(self, disk, blk_list, instance_info, is_ceph_ephemeral=False):
        # FIXME(toha) This code should be cleaned up and covered by unit tests
        disk_path = None
        if not is_ceph_ephemeral:
            disk = "/" + disk
            for i in blk_list:
                if instance_info['id'] + disk == i[-(LEN_UUID_INSTANCE+len(disk)):]:
                    disk_path = i
                if instance_info['OS-EXT-SRV-ATTR:instance_name'] + disk == \
                        i[-(len(instance_info['OS-EXT-SRV-ATTR:instance_name'])+len(disk)):]:
                    disk_path = i
        else:
            disk = "_" + disk
            for i in blk_list:
                if ("compute/%s%s" % (instance_info['id'], disk)) == i:
                    disk_path = i
        return disk_path

    def get_flavor_from_id(self, flavor_id):
        return self.nova_client.flavors.get(flavor_id)

    def get_flavor_list(self, **kwargs):
        return self.nova_client.flavors.list(**kwargs)

    def create_flavor(self, **kwargs):
        return self.nova_client.flavors.create(**kwargs)

    def delete_flavor(self, flavor_id):
        self.nova_client.flavors.delete(flavor_id)

    def wait_for_status(self, getter, id, status):
        # FIXME(toha) What if it is infinite loop here?
        while getter.get(id).status != status:
            time.sleep(1)

    def get_status(self, getter, id):
        return getter.get(id).status
