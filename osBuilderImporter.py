from utils import forward_agent, up_ssh_tunnel, ChecksumImageInvalid, CEPH, REMOTE_FILE, QCOW2, log_step, get_log
from fabric.api import run, settings, env
from FileLikeProxy import FileLikeProxy
import time
import ipaddr

__author__ = 'mirrorcoder'

LOG = get_log(__name__)

DISK = "/disk"
LOCAL = ".local"
LEN_UUID_INSTANCE = 36
TEMP_PREFIX = ".temp"


class osBuilderImporter:

    """
    The main class for importing data from source cloud.
    """

    def __init__(self, keystone_client, glance_client, cinder_client, nova_client, network_client, config, config_from, data):
        self.keystone_client = keystone_client
        self.glance_client = glance_client
        self.cinder_client = cinder_client
        self.nova_client = nova_client
        self.network_client = network_client
        self.config = config
        self.config_from = config_from
        self.data = data
        self.data_for_instance = dict()
        self.instance = object()

    @log_step(3, LOG)
    def finish(self):
        LOG.info("| instance be migrated")
        return self.instance

    @log_step(3, LOG)
    def prepare_for_creating_new_instance(self):
        self.data_for_instance["name"] = self.data["name"]
        self.data_for_instance["image"] = self.__get_image(self.data['image'])
        if (self.data['disk']['type'] == CEPH) and ('diff_path' in self.data['disk']):
            self.data_for_instance["image"] = self.__get_image(self.data['disk']['diff_path'])
            self.data['disk']['diff_path'].delete()
        self.data_for_instance["flavor"] = self.__get_flavor(self.__ensure_param(self.data, 'flavor'))
        self.data_for_instance["meta"] = self.__ensure_param(self.data, 'metadata')
        self.data_for_instance["security_groups"] = self.__ensure_param(self.data, 'security_groups')
        self.data_for_instance["key_name"] = self.__get_key_name(self.__ensure_param(self.data, 'key'))
        self.data_for_instance["config_drive"] = self.__ensure_param(self.data, 'config_drive')
        self.data_for_instance["disk_config"] = self.__ensure_param(self.data, 'diskConfig')
        self.data_for_instance["nics"] = self.__prepare_networks(self.data['networks'])
         #availability_zone=self.ensure_param(data, 'availability_zone')
        return self

    @log_step(3, LOG)
    def prepare_for_boot_volume(self):
        self.data_for_instance["block_device_mapping_v2"] = [{
            "source_type": "image",
            "uuid": self.data_for_instance["image"].id,
            "destination_type": "volume",
            "volume_size": self.data["boot_volume_size"],
            "delete_on_termination": True,
            "boot_index": 0
        }]
        self.data_for_instance["image"] = None
        return self

    @log_step(3, LOG)
    def delete_image_from_source_and_dest_cloud(self):
        self.glance_client.images.delete(self.data_for_instance["block_device_mapping_v2"][0]["uuid"])
        self.data['image'].delete()
        return self

    @log_step(3, LOG)
    def create_instance(self):
        LOG.info("  creating new instance")
        LOG.debug("params:")
        for param in self.data_for_instance:
            LOG.debug("%s = %s" % (param, self.data_for_instance[param]))
        self.instance = self.nova_client.servers.create(**self.data_for_instance)
        LOG.info("  wait for instance activating")
        self.__wait_for_status(self.nova_client.servers, self.instance.id, 'ACTIVE')
        return self

    @log_step(3, LOG)
    def import_delta_file(self):

        """ Transfering instance's diff file """

        dest_disk = self.__detect_delta_file(self.instance, False)
        self.__transfer_remote_file(self.instance,
                                    self.data["disk"]["host"],
                                    self.data["disk"]["diff_path"],
                                    dest_disk)
        return self

    @log_step(3, LOG)
    def import_ephemeral_drive(self):
        if not self.config['ephemeral_drives']['ceph']:
            dest_disk_ephemeral = self.__detect_delta_file(self.instance, True)
            if self.data['disk']['type'] == CEPH:
                backing_disk_ephemeral = self.__detect_backing_file(dest_disk_ephemeral, self.instance)
                self.__delete_remote_file_on_compute(dest_disk_ephemeral, self.instance)
                self.__transfer_remote_file(self.instance,
                                            self.data["disk"]["host"],
                                            self.data["disk"]["ephemeral"],
                                            dest_disk_ephemeral)
                self.__diff_rebase(backing_disk_ephemeral, dest_disk_ephemeral, self.instance)
            else:
                self.__transfer_remote_file(self.instance,
                                            self.data["disk"]["host"],
                                            self.data["disk"]["ephemeral"],
                                            dest_disk_ephemeral)
        if self.config['ephemeral_drives']['ceph']:
            self.__transfer_remote_file_to_ceph(self.instance,
                                                self.data["disk"]["host"],
                                                self.data["disk"]["ephemeral"],
                                                self.config['host'],
                                                self.data['disk']['type'] == CEPH)
        return self

    @log_step(4, LOG)
    def __create_diff(self, instance, format_file, backing_file, diff_file):
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("ssh -oStrictHostKeyChecking=no %s  'qemu-img create -f %s -b %s %s'" %
                    (host, format_file, backing_file, diff_file))

    @log_step(4, LOG)
    def __delete_remote_file_on_compute(self, path_file, instance):
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("ssh -oStrictHostKeyChecking=no %s  'rm -rf %s'" % (host, path_file))

    @log_step(4, LOG)
    def __convert_file(self, instance, from_file, to_file, format_file):
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("ssh -oStrictHostKeyChecking=no %s  'qemu-img convert -O %s %s %s'" %
                    (host, format_file, from_file, to_file))

    @log_step(3, LOG)
    def start_instance(self):
        LOG.debug("    Start instance")
        self.instance.start()
        self.__wait_for_status(self.nova_client.servers, self.instance.id, 'ACTIVE')
        return self

    @log_step(3, LOG)
    def stop_instance(self):
        if self.instance.status == 'ACTIVE':
            LOG.info("    instance is active. Stopping.")
            self.instance.stop()
            LOG.debug("    waiting shutoff state of instance")
            self.__wait_for_status(self.nova_client.servers, self.instance.id, 'SHUTOFF')
            LOG.debug("    instance is stopped")
        else:
            LOG.info("    instance is stopped")
        return self

    @log_step(3, LOG)
    def merge_delta_and_image(self):

        """ Merging diff file and base image of instance (ceph case)"""

        diff_disk_path = self.__diff_copy(self.data,
                                          self.data_for_instance,
                                          self.config['host'],
                                          dest_path=self.config['temp'])
        self.__download_image_from_glance(self.data_for_instance, diff_disk_path)
        self.__diff_rebase("%s/baseimage" % diff_disk_path, "%s/disk" % diff_disk_path)
        self.__diff_commit(diff_disk_path)
        if self.config['glance']['convert_to_raw']:
            if self.data_for_instance['image'].disk_format != 'raw':
                self.__convert_image_to_raw(self.data_for_instance, diff_disk_path)
                self.data_for_instance['image'].disk_format = 'raw'
        new_image_id = self.__upload_image_to_glance(diff_disk_path, self.data_for_instance)
        self.data_for_instance["image"] = self.glance_client.images.get(new_image_id)
        return self

    @log_step(4, LOG)
    def __diff_copy(self, data, data_for_instance, dest_host, dest_path="root"):
        dest_path = dest_path + "/" + data_for_instance["image"].id
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("rm -rf %s" % dest_path)
                run("mkdir -p %s" % dest_path)
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' | " +
                     "ssh -oStrictHostKeyChecking=no %s 'dd bs=1M of=%s/disk'") %
                    (data['disk']['host'], data['disk']['diff_path'], dest_host, dest_path))
        return dest_path

    @log_step(4, LOG)
    def __download_image_from_glance(self, data_for_instance, dest_path):
        baseimage_id = data_for_instance["image"].id
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                     "--os-auth-url=http://%s:35357/v2.0 " +
                    "image-download %s > %s/baseimage") %
                    (self.config['user'],
                     self.config['password'],
                     self.config['tenant'],
                     self.config['host'],
                     baseimage_id,
                     dest_path))

    @log_step(4, LOG)
    def __diff_commit(self, dest_path):
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("cd %s && qemu-img commit disk" % dest_path)

    @log_step(4, LOG)
    def __convert_image_to_raw(self, data_for_instance, path_to_image):
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                run("cd %s && qemu-img convert -f %s -O raw baseimage baseimage.tmp" %
                    (path_to_image, data_for_instance['image'].disk_format))
                run("cd %s && mv -f baseimage.tmp baseimage" % path_to_image)

    @log_step(5, LOG)
    def __detect_backing_file(self, dest_disk_ephemeral, instance):
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                out = run("ssh -oStrictHostKeyChecking=no %s 'qemu-img info %s | grep \"backing file\"'" %
                          (host, dest_disk_ephemeral)).split('\n')
                backing_file = ""
                for i in out:
                    print i
                    line_out = i.split(":")
                    if line_out[0] == "backing file":
                        backing_file = line_out[1].replace(" ", "")
                return backing_file

    @log_step(4, LOG)
    def __upload_image_to_glance(self, path_to_image, data_for_instance):
        name = "new" + data_for_instance["image"].name
        image_format = data_for_instance["image"].disk_format
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                out = run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                           "--os-auth-url=http://%s:35357/v2.0 " +
                           "image-create --name %s --disk-format=%s --container-format=bare --file %s/baseimage | " +
                           "grep id") %
                          (self.config['user'],
                           self.config['password'],
                           self.config['tenant'],
                           self.config['host'],
                           name,
                           image_format,
                           path_to_image))
                new_image_id = out.split()[3]
                print new_image_id
        return new_image_id

    @log_step(4, LOG)
    def __diff_rebase(self, baseimage, disk, instance=None):
        cmd = "qemu-img rebase -u -b %s %s" % (baseimage, disk)
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                if instance:
                    host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
                    run("ssh -oStrictHostKeyChecking=no %s '%s'" % (host, cmd))
                else:
                    run(cmd)

    @log_step(5, LOG)
    def __detect_delta_file(self, instance, is_ephemeral):
        LOG.debug("| | sync with remote file")
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        dest_instance_name = getattr(instance, 'OS-EXT-SRV-ATTR:instance_name')
        dest_disk = None
        with settings(host_string=self.config['host']):
            with forward_agent(env.key_filename):
                out = run("ssh -oStrictHostKeyChecking=no %s 'virsh domblklist %s'" % (host, dest_instance_name))
                dest_output = out.split()
                path_disk = (DISK + LOCAL) if is_ephemeral else DISK
                for i in dest_output:
                    if instance.id + path_disk == i[-(LEN_UUID_INSTANCE+len(path_disk)):]:
                        dest_disk = i
                if not dest_disk:
                    raise NameError("Can't find suitable name of the destination disk path")
                LOG.debug("    Dest disk %s" % dest_disk)
        return dest_disk

    @log_step(4, LOG)
    def __transfer_remote_file(self, instance, disk_host, source_disk, dest_disk):
        LOG.debug("| | copy file")
        host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                with up_ssh_tunnel(host, self.config['host']):
                    if self.config['transfer_file']['compress'] == "dd":
                        run(("ssh -oStrictHostKeyChecking=no %s 'dd bs=1M if=%s' " +
                             "| ssh -oStrictHostKeyChecking=no -p 9999 localhost 'dd bs=1M of=%s'") %
                            (disk_host, source_disk, dest_disk))
                    elif self.config['transfer_file']['compress'] == "gzip":
                        run(("ssh -oStrictHostKeyChecking=no %s 'gzip -%s -c %s' " +
                             "| ssh -oStrictHostKeyChecking=no -p 9999 localhost 'gunzip | dd bs=1M of=%s'") %
                            (self.config['transfer_file']['level_compress'], disk_host, source_disk, dest_disk))

    @log_step(4, LOG)
    def __transfer_remote_file_to_ceph(self, instance, disk_host, source_disk, dest_host, is_source_ceph):
        temp_dir = source_disk[:-10]
        LOG.debug("    copy ephemeral file to destination ceph")
        with settings(host_string=dest_host):
            with forward_agent(env.key_filename):
                run("rbd rm -p compute %s_disk.local" % instance.id)
        with settings(host_string=self.config_from['host']):
            with forward_agent(env.key_filename):
                if self.config["transfer_ephemeral"]["compress"] == "gzip":
                    if not is_source_ceph:
                        run(("ssh -oStrictHostKeyChecking=no %s 'cd %s && " +
                            "qemu-img convert -O raw %s disk.local.temp && gzip -%s -c disk.local.temp' | " +
                            "ssh -oStrictHostKeyChecking=no %s 'gunzip | " +
                            "rbd import --image-format=2 - compute/%s_disk.local'")
                            % (disk_host,
                               temp_dir,
                               source_disk,
                               self.config["transfer_ephemeral"]["level_compress"],
                               dest_host,
                               instance.id))
                    else:
                        run(("gzip -%s -c %s | " +
                            "ssh -oStrictHostKeyChecking=no %s 'gunzip | " +
                            "rbd import --image-format=2 - compute/%s_disk.local'")
                            % (self.config["transfer_ephemeral"]["level_compress"],
                               source_disk,
                               dest_host,
                               instance.id))
                elif self.config["transfer_ephemeral"]["compress"] == "dd":
                    if not source_disk:
                        run(("ssh -oStrictHostKeyChecking=no %s 'cd %s && " +
                            "qemu-img convert -O raw %s disk.local.temp && dd bs=1M if=disk.local.temp' | " +
                            "ssh -oStrictHostKeyChecking=no %s '" +
                            "rbd import --image-format=2 - compute/%s_disk.local'")
                            % (disk_host, temp_dir, source_disk, dest_host, instance.id))
                    else:
                        run(("dd bs=1M if=%s | " +
                            "ssh -oStrictHostKeyChecking=no %s '" +
                            "rbd import --image-format=2 - compute/%s_disk.local'")
                            % (source_disk,
                               dest_host,
                               instance.id))
                run("rm -f %s" % source_disk)

    @log_step(3, LOG)
    def import_volumes(self):

        """
            Volumes migration through image-service.
            Firstly: transferring image from source glance to destination glance
            Secandary: create volume with referencing on to image, in which we already uploaded cinder
            volume on source cloud.
        """
        for source_volume in self.data['volumes']:
            LOG.debug("      volume %s" % source_volume.__dict__)
            image = self.__copy_from_glance_to_glance(source_volume)
            volume = self.cinder_client.volumes.create(size=source_volume.size,
                                                       display_name=source_volume.name,
                                                       display_description=source_volume.description,
                                                       volume_type=source_volume.volume_type,
                                                       availability_zone=source_volume.availability_zone,
                                                       imageRef=image.id)
            LOG.debug("        wait for available")
            self.__wait_for_status(self.cinder_client.volumes, volume.id, 'available')
            LOG.debug("        update volume")
            self.__patch_option_bootable_of_volume(volume.id, source_volume.bootable)
            LOG.debug("        attach vol")
            self.nova_client.volumes.create_server_volume(self.instance.id, volume.id, source_volume.device)
            LOG.debug("        wait for using")
            self.__wait_for_status(self.cinder_client.volumes, volume.id, 'in-use')
            LOG.debug("        delete image on source cloud")
            source_volume.delete()
            LOG.debug("        delete image on dest cloud")
            self.glance_client.images.delete(image.id)
            LOG.debug("        done")
        return self

    @log_step(4, LOG)
    def __patch_option_bootable_of_volume(self, volume_id, bootable):
        cmd = 'use cinder;update volumes set volumes.bootable=%s where volumes.id="%s"' % (int(bootable), volume_id)
        self.__cmd_mysql_on_dest_controller(cmd)

    def __cmd_mysql_on_dest_controller(self, cmd):
        with settings(host_string=self.config['host']):
            run('mysql %s %s -e \'%s\'' % (("-u "+self.config['mysql']['user'])
                                           if self.config['mysql']['user'] else "",
                                           "-p"+self.config['mysql']['password']
                                           if self.config['mysql']['password'] else "",
                                           cmd))

    def __ensure_param(self, data, name, rules_name=None):
        if rules_name is None:
            rules_name = name
        import_rules = self.config['import_rules']
        if rules_name in import_rules['overwrite']:
            return import_rules['overwrite'][rules_name]
        if name in data:
            return data[name]
        if rules_name in import_rules['default']:
            return import_rules['default'][rules_name]
        return None

    @log_step(4, LOG)
    def __get_image(self, image_transfer):
        checksum = image_transfer.checksum
        for image in self.glance_client.images.list():
            if image.checksum == checksum:
                return image
        LOG.debug("Data image = %s", image_transfer.__dict__)
        image_dest = self.__copy_from_glance_to_glance(image_transfer)
        LOG.debug("image data = %s", image_dest)
        if image_dest.checksum != checksum:
            LOG.error("Checksums is not equ")
            raise ChecksumImageInvalid(checksum, image_dest.checksum)
        return image_dest

    @log_step(4, LOG)
    def __copy_from_glance_to_glance(self, transfer_object):
        info_image_source = transfer_object.get_info_image()
        # TODO: added check of checksum on source and dest clouds
        return self.glance_client.images.create(name=info_image_source.name + "Migrate",
                                                container_format=info_image_source.container_format,
                                                disk_format=info_image_source.disk_format,
                                                is_public=info_image_source.is_public,
                                                protected=info_image_source.protected,
                                                data=FileLikeProxy(transfer_object,
                                                                   self.__callback_print_progress,
                                                                   self.config['speed_limit']),
                                                size=info_image_source.size)

    def __callback_print_progress(self, size, length, id, name):
        print "Download {0} bytes of {1} ({2}%) - id = {3} name = {4}".format(size, length, size*100/length, id, name)

    @log_step(4, LOG)
    def __get_flavor(self, flavor_name):
        flavor = None
        for flav in self.nova_client.flavors.list():
            print flav
            print flav.name == flavor_name
        try:
            flavor = self.nova_client.flavors.find(name=flavor_name)
        except Exception as e:
            LOG.error("Exp %s" % e)
            LOG.error("NotFoundFlavor %s" % flavor_name)

        return flavor

    @log_step(4, LOG)
    def __get_key_name(self, key):
        if 'public_key' in key:
            pass  # TODO must import this key
        return key['name']

    @log_step(4, LOG)
    def __prepare_networks(self, networks_info):
        LOG.debug("networks_info %s" % networks_info)
        params = []
        for i in range(0, len(networks_info)):
            net_overwrite = self.config['import_rules']['overwrite']['networks']
            if net_overwrite and (len(net_overwrite) > i):
                network_info = self.config['import_rules']['overwrite']['networks'][i]
            else:
                network_info = networks_info[i]
            network = self.__get_network(network_info, keep_ip=self.config['keep_ip'])
            LOG.debug("    network %s [%s]" % (network['name'], network['id']))
            for item in self.network_client.list_ports(fields=['network_id', 'mac_address', 'id'])['ports']:
                if (item['network_id'] == network['id']) and (item['mac_address'] == networks_info[i]['mac']):
                    LOG.warn("Port with network_id exists after prev run of script %s" % item)
                    LOG.warn("and will be delete")
                    self.network_client.delete_port(item['id'])
            port = self.network_client.create_port({'port': {'network_id': network['id'],
                                                             'mac_address': networks_info[i]['mac'],
                                                             'fixed_ips': [{"ip_address": networks_info[i]['ip']}]}})['port']
            params.append({'net-id': network['id'], 'port-id': port['id']})
        return params

    @log_step(4, LOG)
    def __get_network(self, network_info, keep_ip=False):
        tenant_id = self.__get_tenant_id_by_name(self.config['tenant'])
        instance_addr = ipaddr.IPAddress(network_info['ip'])
        if keep_ip:
            for i in self.network_client.list_subnets()['subnets']:
                if i['tenant_id'] == tenant_id:
                    if ipaddr.IPNetwork(i['cidr']).Contains(instance_addr):
                        return self.network_client.list_networks(id=i['network_id'])['networks'][0]
        if 'id' in network_info:
            return self.network_client.list_networks(id=network_info['id'])['networks'][0]
        if 'name' in network_info:
            return self.network_client.list_networks(name=network_info['name'])['networks'][0]

    def __get_tenant_id_by_name(self, name):
        for i in self.keystone_client.tenants.list():
            if i.name == name:
                return i.id

    def __wait_for_status(self, getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)
