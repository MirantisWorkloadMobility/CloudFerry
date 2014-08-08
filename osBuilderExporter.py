from utils import forward_agent, CEPH, REMOTE_FILE, log_step, get_log, inspect_func, supertask
from fabric.api import run, settings, env, cd
from osVolumeTransfer import VolumeTransfer
from osImageTransfer import ImageTransfer
import time
import json
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

    def __init__(self, glance_client, cinder_client, nova_client, network_client, instance, config):
        self.glance_client = glance_client
        self.cinder_client = cinder_client
        self.nova_client = nova_client
        self.network_client = network_client
        self.config = config
        self.instance = instance

        self.data = dict()

    def finish(self):
        for f in self.funcs:
            f()
        return self.data

    def get_tasks(self):
        return self.funcs

    def get_state(self):
        return {
            'data': self.data
        }

    @inspect_func
    @log_step(LOG)
    def stop_instance(self):
        if self.__get_status(self.nova_client.servers, self.instance.id).lower() == 'active':
            self.instance.stop()
        LOG.debug("wait for instance shutoff")
        self.__wait_for_status(self.nova_client.servers, self.instance.id, 'SHUTOFF')
        return self

    @inspect_func
    @log_step(LOG)
    def get_name(self):
        self.data['name'] = getattr(self.instance, 'name')
        return self

    @inspect_func
    @log_step(LOG)
    def get_metadata(self):
        self.data['metadata'] = getattr(self.instance, 'metadata')
        return self

    @inspect_func
    @log_step(LOG)
    def get_availability_zone(self):
        self.data['availability_zone'] = getattr(self.instance, 'OS-EXT-AZ:availability_zone')
        return self

    @inspect_func
    @log_step(LOG)
    def get_config_drive(self):
        self.data['config_drive'] = getattr(self.instance, 'config_drive')
        return self

    @inspect_func
    @log_step(LOG)
    def get_disk_config(self):
        self.data['disk_config'] = getattr(self.instance, 'OS-DCF:diskConfig')
        return self

    @inspect_func
    @log_step(LOG)
    def get_instance_name(self):
        self.data['instance_name'] = getattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name')
        return self

    @inspect_func
    @log_step(LOG)
    def get_image(self):
        if self.instance.image:
            self.data['image'] = ImageTransfer(self.instance.image['id'], self.glance_client)
            self.data['boot_from_volume'] = False
        else:
            self.data['image'] = None
            self.data['boot_from_volume'] = True
        return self

    @inspect_func
    @log_step(LOG)
    def get_flavor(self):
        self.data['flavor'] = self.__get_flavor_from_instance(self.instance).name
        return self

    @inspect_func
    @log_step(LOG)
    def get_security_groups(self):
        self.data['security_groups'] = [security_group['name'] for security_group in self.instance.security_groups]
        return self

    @inspect_func
    @log_step(LOG)
    def get_key(self):
        self.data['key'] = {'name': self.instance.key_name}
        return self

    @inspect_func
    @log_step(LOG)
    def get_networks(self):
        networks = []

        for network in self.instance.networks.items():
            networks.append({
                'name': network[0],
                'ip': network[1][0],
                'mac': self.__get_mac_by_ip(network[1][0])
            })

        self.data['networks'] = networks
        return self

    @inspect_func
    @log_step(LOG)
    def get_disk(self):
        """Getting information about diff file of source instance"""
        is_ephemeral = self.__get_flavor_from_instance(self.instance).ephemeral > 0
        if not self.data["boot_from_volume"]:
            if self.config["ephemeral_drives"]['ceph']:
                diff_path = self.__get_instance_diff_path(self.instance, False, True)
                ephemeral = self.__get_instance_diff_path(self.instance, True, True) if is_ephemeral else None
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
                diff_path = self.__get_instance_diff_path(self.instance, False, False)
                ephemeral = self.__get_instance_diff_path(self.instance, True, False) if is_ephemeral else None
                self.data['disk'] = {
                    'type': REMOTE_FILE,
                    'host': getattr(self.instance, 'OS-EXT-SRV-ATTR:host'),
                    'diff_path': diff_path,
                    'ephemeral': ephemeral
                }
        else:
            ephemeral = self.__get_instance_diff_path(self.instance, True, self.config["ephemeral_drives"]['ceph']) \
                if is_ephemeral else None
            self.__create_temp_directory(self.config['temp'])
            self.data['disk'] = {
                'type': CEPH if self.config["ephemeral_drives"]['ceph'] else REMOTE_FILE,
                'host': self.config['host'] if self.config["ephemeral_drives"]['ceph']
                else getattr(self.instance, 'OS-EXT-SRV-ATTR:host'),
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
        print diff_path, temp_path, image_format, name
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
    def get_volumes(self):

        """
            Gathering information about attached volumes to source instance and upload these volumes
            to Glance for further importing through image-service on to destination cloud.
        """
        images_from_volumes = []
        for volume_info in self.nova_client.volumes.get_server_volumes(self.instance.id):
            volume = self.cinder_client.volumes.get(volume_info.volumeId)
            LOG.debug("| | uploading volume %s [%s] to image service bootable=%s" %
                      (volume.display_name, volume.id, volume.bootable))
            resp, image = self.cinder_client.volumes.upload_to_image(volume=volume,
                                                                     force=True,
                                                                     image_name=volume.id,
                                                                     container_format="bare",
                                                                     disk_format=self.config['cinder']['disk_format'])
            image_upload = image['os-volume_upload_image']
            self.__wait_for_status(self.glance_client.images, image_upload['image_id'], 'active')
            if self.config["cinder"]["backend"] == "ceph":
                image_from_glance = self.glance_client.images.get(image_upload['image_id'])
                with settings(host_string=self.config['host']):
                    out = json.loads(run("rbd -p images info %s --format json" % image_upload['image_id']))
                    image_from_glance.update(size=out["size"])
            if (volume.bootable != "true") or (not self.data["boot_from_volume"]):
                images_from_volumes.append(VolumeTransfer(volume,
                                                          self.instance,
                                                          image_upload['image_id'],
                                                          self.glance_client))
            else:
                self.data['image'] = ImageTransfer(image_upload['image_id'], self.glance_client)
                self.data['boot_volume_size'] = volume.size

        self.data['volumes'] = images_from_volumes
        return self

    @log_step(LOG)
    def __get_flavor_from_instance(self, instance):
        return self.nova_client.flavors.get(instance.flavor['id'])

    @log_step(LOG)
    def __get_instance_diff_path(self, instance, is_ephemeral, is_ceph_ephemeral):

        """Return path of instance's diff file"""

        disk_host = getattr(self.instance, 'OS-EXT-SRV-ATTR:host')
        libvirt_name = getattr(self.instance, 'OS-EXT-SRV-ATTR:instance_name')
        source_disk = None
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                out = run("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'" %
                          (disk_host, libvirt_name))
                source_out = out.split()
                path_disk = (DISK + LOCAL) if is_ephemeral else DISK
                if not is_ceph_ephemeral:
                    path_disk = "/" + path_disk
                    for i in source_out:
                        if instance.id + path_disk == i[-(LEN_UUID_INSTANCE+len(path_disk)):]:
                            source_disk = i
                else:
                    path_disk = "_" + path_disk
                    for i in source_out:
                        if ("compute/%s%s" % (instance.id, path_disk)) == i:
                            source_disk = i
                if not source_disk:
                    raise NameError("Can't find suitable name of the source disk path")
        return source_disk

    def __get_mac_by_ip(self, ip_address):
        for port in self.port_list:
            if port["fixed_ips"][0]["ip_address"] == ip_address:
                return port["mac_address"]

    def __get_status(self, getter, id):
        return getter.get(id).status

    def __wait_for_status(self, getter, id, status):
        while self.__get_status(getter, id) != status:
            time.sleep(1)

    def __getattr__(self, item):
        getter = {
            'port_list': lambda: self.network_client.list_ports()["ports"]
        }[item]

        if getter is None:
            raise AttributeError("Exporter has no attribute %s" % item)

        return getter()
