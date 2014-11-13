from cloudferrylib.base.action import action
from cloudferrylib.os.actions import transport_ceph_to_ceph_via_ssh
from cloudferrylib.os.actions import transport_ceph_to_file_via_ssh
from cloudferrylib.os.actions import transport_file_to_ceph_via_ssh
from cloudferrylib.os.actions import transport_file_to_file_via_ssh
from cloudferrylib.os.actions import convert_image_to_file
from cloudferrylib.os.actions import convert_file_to_image
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.utils import utils as utl, forward_agent

from fabric.api import run, settings, env
from cloudferrylib.utils import utils as utl
import copy
from fabric.api import run, settings

CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
ISCSI = 'iscsi'
COMPUTE = 'compute'
INSTANCES = 'instances'
INSTANCE_BODY = 'instance'
INSTANCE = 'instance'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
DIFF_OLD = 'diff_old'
EPHEMERAL_OLD = 'ephemeral_old'

PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
HOST_SRC = 'host_src'

TEMP = 'temp'
BOOT_VOLUME = 'boot_volume'
FLAVORS = 'flavors'
BOOT_IMAGE = 'boot_image'


TRANSPORTER_MAP = {CEPH: {CEPH: transport_ceph_to_ceph_via_ssh.TransportCephToCephViaSsh(),
                          ISCSI: transport_ceph_to_file_via_ssh.TransportCephToFileViaSsh()},
                   ISCSI: {CEPH: transport_file_to_ceph_via_ssh.TransportFileToCephViaSsh(),
                           ISCSI: transport_file_to_file_via_ssh.TransportFileToFileViaSsh()}}


class TransportInstance(action.Action):
    # TODO constants

    @staticmethod
    def mapping_compute_info(src_cloud, dst_cloud, compute_info):

        new_compute_info = copy.deepcopy(compute_info)

        src_compute = src_cloud.resources[utl.COMPUTE_RESOURCE]
        dst_compute = dst_cloud.resources[utl.COMPUTE_RESOURCE]

        src_flavors_dict = \
            {flavor.id: flavor.name for flavor in src_compute.get_flavor_list()}

        dst_flavors_dict = \
            {flavor.name: flavor.id for flavor in dst_compute.get_flavor_list()}

        for instance in new_compute_info['instances'].values():
            _instance = instance['instance']
            flavor_name = src_flavors_dict[_instance['flavor_id']]
            _instance['flavor_id'] = dst_flavors_dict[flavor_name]

        return new_compute_info

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, info=None, **kwargs):
        info = copy.deepcopy(info)
        #Init before run
        dst_storage = cloud_dst.resources[utl.STORAGE_RESOURCE]
        src_compute = cloud_src.resources[utl.COMPUTE_RESOURCE]
        backend_ephem_drv_src = src_compute.config.compute.backend
        backend_storage_dst = dst_storage.config.storage.backend

        #Mapping another params(flavors, etc)
        info[COMPUTE] = self.mapping_compute_info(cloud_src, cloud_dst, compute_info=info[COMPUTE])

        compute_info = info[COMPUTE]

        #Get next one instance
        instance_id = compute_info[INSTANCES].iterkeys().next()
        instance_boot = BOOT_IMAGE \
            if compute_info[INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id'] \
            else BOOT_VOLUME
        is_ephemeral = compute_info[INSTANCES][instance_id][utl.INSTANCE_BODY]['is_ephemeral']

        if instance_boot == BOOT_IMAGE:
            if backend_ephem_drv_src == CEPH:
                self.transport_image(cfg, cloud_src, cloud_dst, info, instance_id)
                info = self.deploy_instance(cloud_dst, info)
            elif backend_ephem_drv_src == ISCSI:
                if backend_storage_dst == CEPH:
                    self.transport_diff_and_merge(cfg, cloud_src, cloud_dst, info, instance_id)
                    info = self.deploy_instance(cloud_dst, info)
                elif backend_storage_dst == ISCSI:
                    info = self.deploy_instance(cloud_dst, info)
                    self.copy_diff_file(cfg, cloud_src, cloud_dst, info)
        elif instance_boot == BOOT_VOLUME:
            info = self.transport_boot_volume_src_to_dst(cloud_src, cloud_dst, info, instance_id)
            info = self.deploy_instance(cloud_dst, info)

        if is_ephemeral:
            self.copy_ephemeral(cfg, cloud_src, cloud_dst, info)

        # self.start_instance(cloud_dst, info, instance_id)
        return {
            'info': info
        }

    def deploy_instance(self, cloud_dst, info):
        info = copy.deepcopy(info)
        dst_compute = cloud_dst.resources[COMPUTE]

        new_ids = dst_compute.deploy(info)
        for i in new_ids.iterkeys():
            dst_compute.wait_for_status(i, 'active')
        new_info = dst_compute.read_info(search_opts={'id': new_ids.keys()})
        for i in new_ids.iterkeys():
            dst_compute.change_status('shutoff', instance_id=i)
        info = self.prepare_ephemeral_drv(info, new_info, new_ids)
        return info

    def prepare_ephemeral_drv(self, info, new_info, map_new_to_old_ids):
        info = copy.deepcopy(info)
        new_info = copy.deepcopy(new_info)
        for new_id, old_id in map_new_to_old_ids.iteritems():
            instance_old = info[COMPUTE][INSTANCES][old_id]
            instance_new = new_info[COMPUTE][INSTANCES][new_id]

            ephemeral_path_dst = instance_new[EPHEMERAL][PATH_SRC]
            instance_new[EPHEMERAL][PATH_DST] = ephemeral_path_dst            
            ephemeral_host_dst = instance_new[EPHEMERAL][HOST_SRC]
            instance_new[EPHEMERAL][HOST_DST] = ephemeral_host_dst
            
            diff_path_dst = instance_new[DIFF][PATH_SRC]
            instance_new[DIFF][PATH_DST] = diff_path_dst            
            diff_host_dst = instance_new[DIFF][HOST_SRC]
            instance_new[DIFF][HOST_DST] = diff_host_dst

            ephemeral_path_src = instance_old[EPHEMERAL][PATH_SRC]
            instance_new[EPHEMERAL][PATH_SRC] = ephemeral_path_src            
            ephemeral_host_src = instance_old[EPHEMERAL][HOST_SRC]
            instance_new[EPHEMERAL][HOST_SRC] = ephemeral_host_src
            
            diff_path_src = instance_old[DIFF][PATH_SRC]
            instance_new[DIFF][PATH_SRC] = diff_path_src            
            diff_host_src = instance_old[DIFF][HOST_SRC]
            instance_new[DIFF][HOST_SRC] = diff_host_src

        return new_info

    def delete_remote_file_on_compute(self, path_file, host_cloud, host_instance):
        with settings(host_string=host_cloud):
            with forward_agent(env.key_filename):
                run("ssh -oStrictHostKeyChecking=no %s  'rm -rf %s'" % (host_instance, path_file))

    def find_id_by_old_id(self, info, old_id):
        for key, value in info.iteritems():
            if value['old_id'] == old_id:
                return key
        return None

    def transport_boot_volume_src_to_dst(self, cloud_src, cloud_dst, info, instance_id):
        info = copy.deepcopy(info)
        instance = info[utl.COMPUTE_RESOURCE][utl.INSTANCES_TYPE][instance_id]

        src_storage = cloud_src.resources[utl.STORAGE_RESOURCE]
        volume = src_storage.read_info(id=instance[INSTANCE_BODY]['volumes'][0]['id'])

        act_v_to_i = convert_volume_to_image.ConverterVolumeToImage('qcow2', cloud_src)
        image = act_v_to_i.run(volume)['image_data']

        act_g_to_g = copy_g2g.CopyFromGlanceToGlance(cloud_src, cloud_dst)
        image_dst = act_g_to_g.run(image)['images_info']
        instance[utl.META_INFO][utl.IMAGE_BODY] = image_dst['image']['images'].values()[0]

        return info

    def copy_data_via_ssh(self, cfg, cloud_src, cloud_dst, info, body, resources, types):
        dst_storage = cloud_dst.resources[resources]
        src_compute = cloud_src.resources[resources]
        src_backend = src_compute.config.compute.backend
        dst_backend = dst_storage.config.compute.backend
        transporter = TRANSPORTER_MAP[src_backend][dst_backend]
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=resources,
                        resource_name=types,
                        resource_root_name=body)

    def copy_diff_file(self, cfg, cloud_src, cloud_dst, info):
        self.copy_data_via_ssh(cfg,
                               cloud_src,
                               cloud_dst,
                               info,
                               utl.DIFF_BODY,
                               utl.COMPUTE_RESOURCE,
                               utl.INSTANCES_TYPE)

    def copy_ephemeral(self, cfg, cloud_src, cloud_dst, info):
        dst_storage = cloud_dst.resources[utl.COMPUTE_RESOURCE]
        src_compute = cloud_src.resources[utl.COMPUTE_RESOURCE]
        src_backend = src_compute.config.compute.backend
        dst_backend = dst_storage.config.compute.backend
        if (src_backend == CEPH) and (dst_backend == ISCSI):
            self.copy_ephemeral_ceph_to_iscsi(cfg, cloud_src, cloud_dst, info)
        elif (src_backend == ISCSI) and (dst_backend == CEPH):
            self.copy_ephemeral_iscsi_to_ceph(cfg, cloud_src, cloud_dst, info)
        else:
            self.copy_data_via_ssh(cfg,
                                   cloud_src,
                                   cloud_dst,
                                   info,
                                   utl.EPHEMERAL_BODY,
                                   utl.COMPUTE_RESOURCE,
                                   utl.INSTANCES_TYPE)

    def copy_ephemeral_ceph_to_iscsi(self, cfg, cloud_src, cloud_dst, info):
        instances = info[utl.COMPUTE_RESOURCE][utl.INSTANCES_TYPE]
        qemu_img_dst = cloud_dst.qemu_img
        qemu_img_src = cloud_src.qemu_img
        temp_src = cloud_src.cloud_config.cloud.temp
        host_dst = cloud_dst.getIpSsh()
        transporter = TRANSPORTER_MAP[ISCSI][ISCSI]
        temp_path_src = temp_src+"/%s"+utl.DISK_EPHEM
        for inst_id, inst in instances.iteritems():
            path_src_id_temp = temp_path_src % inst_id
            host_compute_dst = inst[EPHEMERAL][HOST_DST]
            backing_file = qemu_img_dst.detect_backing_file(inst[EPHEMERAL][PATH_DST], host_compute_dst)
            self.delete_remote_file_on_compute(inst[EPHEMERAL][PATH_DST], host_dst, host_compute_dst)
            qemu_img_src.convert(utl.QCOW2, 'rbd:%s' % inst[EPHEMERAL][PATH_SRC], path_src_id_temp)
            inst[EPHEMERAL][PATH_SRC] = path_src_id_temp
            transporter.run(cfg=cfg,
                            cloud_src=cloud_src,
                            cloud_dst=cloud_dst,
                            info=info,
                            resource_type=utl.COMPUTE_RESOURCE,
                            resource_name=utl.INSTANCES_TYPE,
                            resource_root_name=utl.EPHEMERAL_BODY)
            qemu_img_dst.diff_rebase(backing_file, inst[EPHEMERAL][PATH_DST], host_compute_dst)

    def copy_ephemeral_iscsi_to_ceph(self, cfg, cloud_src, cloud_dst, info):
        instances = info[utl.COMPUTE_RESOURCE][utl.INSTANCES_TYPE]
        qemu_img_src = cloud_src.qemu_img
        temp_src = cloud_src.cloud_config.cloud.temp
        transporter = TRANSPORTER_MAP[ISCSI][ISCSI]
        temp_path_src = temp_src+"/%s"+utl.DISK_EPHEM
        for inst_id, inst in instances.iteritems():
            path_src_id_temp = temp_path_src % inst_id
            path_src = inst[EPHEMERAL][PATH_SRC]
            host_src = inst[EPHEMERAL][HOST_SRC]
            qemu_img_src.convert(utl.RAW, path_src, path_src_id_temp, host_src)
            inst[EPHEMERAL][PATH_SRC] = path_src_id_temp
            transporter.run(cfg=cfg,
                            cloud_src=cloud_src,
                            cloud_dst=cloud_dst,
                            info=info,
                            resource_type=utl.COMPUTE_RESOURCE,
                            resource_name=utl.INSTANCES_TYPE,
                            resource_root_name=utl.EPHEMERAL_BODY)

    def transport_from_src_to_dst(self, cfg, cloud_src, cloud_dst, info):
        transporter = transport_file_to_file_via_ssh.TransportFileToFileViaSsh()
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=utl.COMPUTE_RESOURCE,
                        resource_name=utl.INSTANCES_TYPE,
                        resource_root_name=utl.DIFF_BODY)

    def transport_diff_and_merge(self, cfg, cloud_src, cloud_dst, info, instance_id):
        image_id = info[COMPUTE][INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id']
        cloud_cfg_dst = cloud_dst.cloud_config.cloud
        temp_dir_dst = cloud_cfg_dst.temp
        host_dst = cloud_cfg_dst.host

        base_file = "%s/%s" % (temp_dir_dst, "temp%s_base" % instance_id)
        diff_file = "%s/%s" % (temp_dir_dst, "temp%s" % instance_id)

        info[COMPUTE][INSTANCES][instance_id][DIFF][PATH_DST] = diff_file
        info[COMPUTE][INSTANCES][instance_id][DIFF][HOST_DST] = cloud_dst.getIpSsh()

        image_res = cloud_dst.resources[utl.IMAGE_RESOURCE]

        images = image_res.read_info(image_id=image_id)
        image = images[utl.IMAGE_RESOURCE][utl.IMAGES_TYPE][image_id]
        disk_format = image[utl.IMAGE_BODY]['disk_format']

        self.convert_image_to_file(cloud_dst, image_id, base_file)

        self.transport_from_src_to_dst(cfg, cloud_src, cloud_dst, info)

        self.merge_file(cloud_dst, base_file, diff_file)
        if image_res.config.image.convert_to_raw:
            if disk_format.lower() != utl.RAW:
                self.convert_file_to_raw(host_dst, disk_format, base_file)
                disk_format = utl.RAW

        dst_image_id = self.convert_file_to_image(cloud_dst, base_file, disk_format, instance_id)

        info[COMPUTE][INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = dst_image_id

    def convert_file_to_image(self, cloud_dst, base_file, disk_format, instance_id):
        converter = convert_file_to_image.ConvertFileToImage(cloud_dst)
        dst_image_id = converter.run(file_path=base_file,
                                     image_format=disk_format,
                                     image_name="%s-image" % instance_id)
        return dst_image_id

    def convert_image_to_file(self, cloud, image_id, filename):
        convertor = convert_image_to_file.ConvertImageToFile(cloud)
        convertor.run(image_id=image_id,
                      base_filename=filename)

    def merge_file(self, cloud, base_file, diff_file):
        host = cloud.cloud_config.cloud.host
        self.rebase_diff_file(host, base_file, diff_file)
        self.commit_diff_file(host, diff_file)

    def transport_image(self, cfg, cloud_src, cloud_dst, info, instance_id):
        cloud_cfg_dst = cloud_dst.cloud_config.cloud
        temp_dir_dst = cloud_cfg_dst.temp
        transporter = transport_ceph_to_file_via_ssh.TransportCephToFileViaSsh()
        path_dst = "%s/%s" % (temp_dir_dst, "temp%s" % instance_id)
        info[COMPUTE][INSTANCES][instance_id][DIFF][PATH_DST] = path_dst
        info[COMPUTE][INSTANCES][instance_id][DIFF][HOST_DST] = cloud_dst.getIpSsh()
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=utl.COMPUTE_RESOURCE,
                        resource_name=utl.INSTANCES_TYPE,
                        resource_root_name=utl.DIFF_BODY)
        converter = convert_file_to_image.ConvertFileToImage(cloud_dst)
        dst_image_id = converter.run(file_path=path_dst,
                                     image_format='raw',
                                     image_name="%s-image" % instance_id)
        info[COMPUTE][INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = dst_image_id

    def convert_file_to_raw(self, host, disk_format, filepath):
        with settings(host_string=host):
            with forward_agent(env.key_filename):
                run("qemu-img convert -f %s -O raw %s %s.tmp" %
                    (disk_format, filepath, filepath))
                run("mv -f %s.tmp %s" % (filepath, filepath))

    def rebase_diff_file(self, host, base_file, diff_file):
        cmd = "qemu-img rebase -u -b %s %s" % (base_file, diff_file)
        with settings(host_string=host):
            run(cmd)

    def commit_diff_file(self, host, diff_file):
        with settings(host_string=host):
            run("qemu-img commit %s" % diff_file)        
