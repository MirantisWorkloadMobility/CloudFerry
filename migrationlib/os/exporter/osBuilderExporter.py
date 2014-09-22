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
import json

from utils import forward_agent, CEPH, REMOTE_FILE, log_step, get_log
from scheduler.builder_wrapper import inspect_func, supertask
from fabric.api import run, settings, env, cd
from migrationlib.os.utils.osVolumeTransfer import VolumeTransferDirectly, VolumeTransferViaImage
from migrationlib.os.utils.osImageTransfer import ImageTransfer

__author__ = 'mirrorcoder'

LOG = get_log(__name__)

DISK = "disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36


class osBuilderExporter:

    """
    The main class for gathering information from source cloud.
    data -- main dictionary for filling with information from source cloud
    """

    def __init__(self, glance_client, cinder_client, nova_client, network_client, instance, config, data=dict()):
        self.glance_client = glance_client
        self.cinder_client = cinder_client
        self.nova_client = nova_client
        self.network_client = network_client
        self.config = config
        self.instance = instance
        self.funcs = []

        self.data = data

    def finish(self):
        for f in self.funcs:
            f()
        self.funcs = []
        return self.data

    def get_tasks(self):
        return self.funcs

    def set_state(self, obj_dict):
        self.data = obj_dict['data']

    def get_state(self):
        return {
            'data': self.data
        }

    def convert_to_dict(self):
        res = self.get_state()
        res['_type_class'] = osBuilderExporter.__name__
        return res

    @inspect_func
    @log_step(LOG)
    def stop_instance(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        if self.__get_status(self.nova_client.servers, instance.id).lower() == 'active':
            instance.stop()
        LOG.debug("wait for instance shutoff")
        self.__wait_for_status(self.nova_client.servers, instance.id, 'SHUTOFF')
        return self

    @inspect_func
    @log_step(LOG)
    def get_name(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['name'] = getattr(instance, 'name')
        return self

    @inspect_func
    @log_step(LOG)
    def get_metadata(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['metadata'] = getattr(instance, 'metadata')
        return self

    @inspect_func
    @log_step(LOG)
    def get_availability_zone(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['availability_zone'] = getattr(instance, 'OS-EXT-AZ:availability_zone') \
            if hasattr(instance, 'OS-EXT-AZ:availability_zone') else None
        return self

    @inspect_func
    @log_step(LOG)
    def get_config_drive(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['config_drive'] = getattr(instance, 'config_drive')
        return self

    @inspect_func
    @log_step(LOG)
    def get_disk_config(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['disk_config'] = getattr(instance, 'OS-DCF:diskConfig')
        return self

    @inspect_func
    @log_step(LOG)
    def get_instance_name(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['instance_name'] = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        return self

    @inspect_func
    @log_step(LOG)
    def get_image(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        if instance.image:
            self.data['image'] = ImageTransfer(instance.image['id'], self.glance_client)
            self.data['boot_from_volume'] = False
        else:
            self.data['image'] = None
            self.data['boot_from_volume'] = True
        return self

    @inspect_func
    @log_step(LOG)
    def get_flavor(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['flavor'] = self.__get_flavor_from_instance(instance).name
        return self

    @inspect_func
    @log_step(LOG)
    def get_security_groups(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['security_groups'] = [security_group['name'] for security_group in instance.security_groups]
        return self

    @inspect_func
    @log_step(LOG)
    def get_key(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['key'] = {'name': instance.key_name}
        return self

    @inspect_func
    @log_step(LOG)
    def get_networks(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        networks = []
        func_mac_address = self.__get_func_mac_address(instance)
        for network in self.instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': func_mac_address(network[1][0])
            })

        self.data['networks'] = networks
        return self

    @inspect_func
    @log_step(LOG)
    def get_disk(self, instance=None, data=None, **kwargs):
        """Getting information about diff file of source instance"""
        instance = instance if instance else self.instance
        boot_from_volume = data['boot_from_volume'] if data else self.data['boot_from_volume']
        is_ephemeral = self.__get_flavor_from_instance(instance).ephemeral > 0

        if not boot_from_volume:
            if self.config["ephemeral_drives"]['ceph']:
                diff_path = self.__get_instance_diff_path(instance, False, True)
                ephemeral = self.__get_instance_diff_path(instance, True, True) if is_ephemeral else None
                self.__create_temp_directory(self.config['temp'])
                self.data['disk'] = {
                    'type': CEPH,
                    'host': self.config['host'],
                    'diff_path': self.__transfer_rbd_to_glance(diff_path,
                                                               self.config['temp'],
                                                               self.config['ephemeral_drives']['convert_diff_file'],
                                                               "diff_path"),
                    'ephemeral': self.__transfer_rbd_to_file(ephemeral,
                                                             self.config['temp'],
                                                             self.config['ephemeral_drives']['convert_ephemeral_drive'],
                                                             "disk.local")
                }
            else:
                diff_path = self.__get_instance_diff_path(instance, False, False)
                ephemeral = self.__get_instance_diff_path(instance, True, False) if is_ephemeral else None
                self.data['disk'] = {
                    'type': REMOTE_FILE,
                    'host': getattr(instance, 'OS-EXT-SRV-ATTR:host'),
                    'diff_path': diff_path,
                    'ephemeral': ephemeral
                }
        else:
            ephemeral = self.__get_instance_diff_path(instance, True, self.config["ephemeral_drives"]['ceph']) \
                if is_ephemeral else None
            self.__create_temp_directory(self.config['temp'])
            self.data['disk'] = {
                'type': CEPH if self.config["ephemeral_drives"]['ceph'] else REMOTE_FILE,
                'host': self.config['host'] if self.config["ephemeral_drives"]['ceph']
                else getattr(instance, 'OS-EXT-SRV-ATTR:host'),
                'ephemeral': self.__transfer_rbd_to_file(ephemeral,
                                                         self.config['temp'],
                                                         self.config['ephemeral_drives']['convert_ephemeral_drive'],
                                                         "disk.local")
                if self.config["ephemeral_drives"]['ceph'] else ephemeral
            }
            self.data["boot_volume_size"] = {}
        return self

    @log_step(LOG)
    def __create_temp_directory(self, temp_path):
        with settings(host_string=self.config['host']):
            run("rm -rf %s" % temp_path)
            run("mkdir -p %s" % temp_path)

    @log_step(LOG)
    def __transfer_rbd_to_glance(self, diff_path, temp_path, image_format, name):
        name_file_diff_path = "disk"
        self.__transfer_rbd_to_file(diff_path, temp_path, image_format, name_file_diff_path)
        with settings(host_string=self.config['host']):
            with cd(temp_path):
                out = run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                           "--os-auth-url=http://%s:35357/v2.0 " +
                           "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                           "grep id") %
                          (self.config['user'],
                           self.config['password'],
                           self.config['tenant'],
                           self.config['host'],
                           name,
                           image_format,
                           name_file_diff_path))
                id = out.split("|")[2].replace(' ', '')
                return ImageTransfer(id, self.glance_client)

    @log_step(LOG)
    def __transfer_rbd_to_file(self, diff_path, temp_path, image_format, name_file_diff_path):
        if not diff_path:
            return None
        with settings(host_string=self.config['host']):
            with cd(temp_path):
                run("qemu-img convert -O %s rbd:%s %s" % (image_format, diff_path, name_file_diff_path))
        if temp_path[-1] == "/":
            return temp_path+name_file_diff_path
        else:
            return temp_path+"/"+name_file_diff_path

    @inspect_func
    @log_step(LOG)
    def get_volumes_via_glance(self, instance=None, **kwargs):
        """
            Gathering information about attached volumes to source instance and upload these volumes
            to Glance for further importing through image-service on to destination cloud.
        """
        instance = instance if instance else self.instance
        images_from_volumes = []
        for volume_info in self.nova_client.volumes.get_server_volumes(instance.id):
            volume = self.cinder_client.volumes.get(volume_info.volumeId)
            LOG.debug("| | uploading volume %s [%s] to image service bootable=%s" %
                      (volume.display_name, volume.id, volume.bootable if hasattr(volume, 'bootable') else False))
            image = self.__upload_volume_to_glance(volume)
            image_upload = image['os-volume_upload_image']
            self.__wait_for_status(self.glance_client.images, image_upload['image_id'], 'active')
            if self.config["cinder"]["backend"] == "ceph":
                image_from_glance = self.glance_client.images.get(image_upload['image_id'])
                with settings(host_string=self.config['host']):
                    out = json.loads(run("rbd -p images info %s --format json" % image_upload['image_id']))
                    image_from_glance.update(size=out["size"])

            if ((volume.bootable if hasattr(volume, 'bootable') else False) != "true") or (not self.data["boot_from_volume"]):
                images_from_volumes.append(VolumeTransferViaImage(volume,
                                                          instance,
                                                          image_upload['image_id'],
                                                          self.glance_client))
            else:
                self.data['image'] = ImageTransfer(image_upload['image_id'], self.glance_client)
                self.data['boot_volume_size'] = volume.size

        self.data['volumes'] = images_from_volumes
        return self

    @log_step(LOG)
    def __upload_volume_to_glance(self, volume):
        resp, image = self.cinder_client.volumes.upload_to_image(volume=volume,
                                                                 force=True,
                                                                 image_name=volume.id,
                                                                 container_format="bare",
                                                                 disk_format=self.config['cinder']['disk_format'])
        return image


    @inspect_func
    @log_step(LOG)
    def get_volumes(self, instance=None, **kwargs):
        instance = instance if instance else self.instance
        self.data['volumes'] = []
        for volume_info in self.nova_client.volumes.get_server_volumes(instance.id):
            volume = self.cinder_client.volumes.get(volume_info.volumeId)
            volume_path = None
            if ((volume.bootable if hasattr(volume, 'bootable') else False) == "true") or (not self.data["boot_from_volume"]):
                image = self.__upload_volume_to_glance(volume)
                image_upload = image['os-volume_upload_image']
                self.__wait_for_status(self.glance_client.images, image_upload['image_id'], 'active')
                if self.config["cinder"]["backend"] == "ceph":
                    image_from_glance = self.glance_client.images.get(image_upload['image_id'])
                    with settings(host_string=self.config['host']):
                        out = json.loads(run("rbd -p images info %s --format json" % image_upload['image_id']))
                        image_from_glance.update(size=out["size"])
                self.data['image'] = ImageTransfer(image_upload['image_id'], self.glance_client)
                self.data['boot_volume_size'] = volume.size
            else:
                if self.config['cinder']['backend'] == 'iscsi':
                    volume_path = self.__get_instance_diff_path(instance, False, False, volume.id)
                self.data['volumes'].append(VolumeTransferDirectly(volume, instance, volume_path))
        return self


    @log_step(LOG)
    def     __get_flavor_from_instance(self, instance):
        return self.nova_client.flavors.get(instance.flavor['id'])

    @log_step(LOG)
    def __get_instance_diff_path(self, instance, is_ephemeral, is_ceph_ephemeral, volume_id=None):

        """Return path of instance's diff file"""

        disk_host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        libvirt_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        source_disk = None
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                out = run("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'" %
                          (disk_host, libvirt_name))
                source_out = out.split()
                path_disk = (DISK + LOCAL) if is_ephemeral else DISK
                if volume_id:
                    path_disk = "volume-" + volume_id
                    for device in source_out:
                        if path_disk in device:
                            return device
                if not is_ceph_ephemeral:
                    path_disk = "/" + path_disk
                    for i in source_out:
                        if instance.id + path_disk == i[-(LEN_UUID_INSTANCE+len(path_disk)):]:
                            source_disk = i
                        if libvirt_name + path_disk == i[-(len(libvirt_name)+len(path_disk)):]:
                            source_disk = i
                else:
                    path_disk = "_" + path_disk
                    for i in source_out:
                        if ("compute/%s%s" % (instance.id, path_disk)) == i:
                            source_disk = i
                if not source_disk:
                    raise NameError("Can't find suitable name of the source disk path")
        return source_disk

    def __get_func_mac_address(self, instance=None):
        is_not_match_client = not type(self.nova_client) == type(self.network_client)
        if is_not_match_client:
            return self.__get_mac_by_ip
        else:
            list_mac = self.__get_mac_nova_network(instance)
            return lambda x: next(list_mac)

    def __get_mac_by_ip(self, ip_address):
        for port in self.port_list:
            if port["fixed_ips"][0]["ip_address"] == ip_address:
                return port["mac_address"]

    def __get_mac_nova_network(self, instance):
        compute_node = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        libvirt_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                cmd = "virsh dumpxml %s | grep 'mac address' | cut -d\\' -f2" % libvirt_name
                out = run("ssh -oStrictHostKeyChecking=no %s %s" %
                          (compute_node, cmd))
                mac_addresses=out.split()
        mac_iter = iter(mac_addresses)
        return mac_iter

    def __get_status(self, getter, id):
        return getter.get(id).status

    def __wait_for_status(self, getter, id, status):
        while self.__get_status(getter, id) != status:
            time.sleep(1)

    def __getattr__(self, item):
        list_getters = {
            'port_list': lambda: self.network_client.list_ports()["ports"]
        }
        getter = None
        if item in list_getters:
            getter = list_getters[item]
        if getter is None:
            raise AttributeError("Exporter has no attribute %s" % item)

        return getter()
