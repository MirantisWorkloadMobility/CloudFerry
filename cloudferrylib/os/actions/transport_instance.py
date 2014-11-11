from cloudferrylib.base.action import action
from cloudferrylib.os.actions import transport_ceph_to_ceph_via_ssh
from cloudferrylib.os.actions import transport_ceph_to_file_via_ssh
from cloudferrylib.os.actions import transport_file_to_ceph_via_ssh
from cloudferrylib.os.actions import transport_file_to_file_via_ssh
from cloudferrylib.os.actions import convert_image_to_file
from cloudferrylib.os.actions import convert_file_to_image
from cloudferrylib.os.actions import converter_volume_to_image
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import prepare_networks
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
PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
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
        src_storage = cloud_src.resources[utl.STORAGE_RESOURCE]
        dst_storage = cloud_dst.resources[utl.STORAGE_RESOURCE]
        src_compute = cloud_src.resources[utl.COMPUTE_RESOURCE]
        dst_compute = cloud_dst.resources[utl.COMPUTE_RESOURCE]

        # if not info:
        #     info = src_compute.read_info()
        #     act_prep_net = prepare_networks.PrepareNetworks(cloud_dst, cfg)
        #     info = act_prep_net.run(info)['info_compute']

        # info = dst_compute.deploy(info, resources_deploy=True)

        compute_info = self.mapping_compute_info(cloud_src, cloud_dst, compute_info=info[COMPUTE])

        instance_id = compute_info[INSTANCES].iterkeys().next()
        instance_boot = BOOT_IMAGE if compute_info[INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id'] else BOOT_VOLUME
        instance = compute_info[INSTANCES][instance_id]

        backend_ephem_drv_src = src_compute.config.compute.backend
        backend_storage_dst = dst_storage.config.storage.backend
        act_v_to_i = converter_volume_to_image.ConverterVolumeToImage('qcow2', cloud_src)
        act_g_to_g = copy_g2g.CopyFromGlanceToGlance(cloud_src, cloud_dst)
        is_ephemeral = compute_info[INSTANCES][instance_id][utl.INSTANCE_BODY]['is_ephemeral']

        one_instance = {
            utl.COMPUTE_RESOURCE: {
                utl.INSTANCES_TYPE: {
                    instance_id: instance
                }
            }
        }

        dst_instance = {
            utl.COMPUTE_RESOURCE: {
                utl.INSTANCES_TYPE: {

                }
            }
        }

        if instance_boot == BOOT_IMAGE:
            if backend_ephem_drv_src == CEPH:
                #Transport D -> I ---> I
                #Deploy Instance
                self.transport_image(cfg, cloud_src, cloud_dst, info, instance_id)
                self.deploy_instance(cloud_dst, info, instance_id)
            elif backend_ephem_drv_src == ISCSI:
                if backend_storage_dst == CEPH:
                    self.transport_diff_and_merge(cfg, cloud_src, cloud_dst, info, instance_id)
                    self.deploy_instance(cloud_dst, info, instance_id)
                    #Transport D ---> Dt
                    #Convert to File B -> Bf
                    #Merge Dt + Bf
                    #Convert to Image Dt -> B
                    #Deploy Instance
                elif backend_storage_dst == ISCSI:
                    info = self.deploy_instance(cloud_dst, info, instance_id)
                    self.copy_diff_file(cfg, cloud_src, cloud_dst, info, backend_ephem_drv_src, backend_storage_dst)
                    #Deploy Instance
                    #Transport D ---> D
        elif instance_boot == BOOT_VOLUME:
            volume = src_storage.read_info(id=instance[INSTANCE_BODY]['volumes'][0]['id'])
            image = act_v_to_i.run(volume)['image_data']
            image_dst = act_g_to_g.run(image)['images_info']
            instance[utl.META_INFO][utl.IMAGE_BODY] = image_dst['image']['images'].values()[0]
            info = dst_compute.deploy(one_instance)
        # TODO: import ephemeral

        if is_ephemeral:
            self.copy_ephemeral(cfg, cloud_src, cloud_dst, info, backend_ephem_drv_src, backend_storage_dst)

        self.start_instance(cloud_dst, info, instance_id)
        return {
            'info': info
        }

    def deploy_instance(self, cloud_dst, info, instance_id):
        dst_compute = cloud_dst.resources[COMPUTE]
        info = dst_compute.deploy(info)
        instance_dst_id = info[COMPUTE][INSTANCES][instance_id]['meta']['dst_id']
        dst_compute.wait_for_status(instance_dst_id, 'active')
        dst_info = dst_compute.read_info(search_opts={'instance_id': instance_dst_id})
        dst_compute.change_status('shutoff', instance_id=instance_dst_id)

        ephemeral_path_dst = dst_info[COMPUTE][INSTANCES][instance_dst_id][EPHEMERAL]['path_src']
        info[COMPUTE][INSTANCES][instance_id][EPHEMERAL][PATH_DST] = ephemeral_path_dst

        diff_path_dst = dst_info[COMPUTE][INSTANCES][instance_dst_id][DIFF]['path_src']
        info[COMPUTE][INSTANCES][instance_id][DIFF][PATH_DST] = diff_path_dst

        ephemeral_host_dst = dst_info[COMPUTE][INSTANCES][instance_dst_id][EPHEMERAL]['host_src']
        info[COMPUTE][INSTANCES][instance_id][EPHEMERAL][HOST_DST] = ephemeral_host_dst

        diff_host_dst = dst_info[COMPUTE][INSTANCES][instance_dst_id][DIFF]['host_src']
        info[COMPUTE][INSTANCES][instance_id][DIFF][HOST_DST] = diff_host_dst

        return info

    def copy_diff_file(self, cfg, cloud_src, cloud_dst, info, src_backend, dst_backend):
        transporter = TRANSPORTER_MAP[src_backend][dst_backend]
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=utl.COMPUTE_RESOURCE,
                        resource_name=utl.INSTANCES_TYPE,
                        resource_root_name=utl.DIFF_BODY)

    def copy_ephemeral(self, cfg, cloud_src, cloud_dst, info, src_backend, dst_backend):
        transporter = TRANSPORTER_MAP[src_backend][dst_backend]
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=utl.COMPUTE_RESOURCE,
                        resource_name=utl.INSTANCES_TYPE,
                        resource_root_name=utl.EPHEMERAL_BODY)

    def transport_diff_and_merge(self, cfg, cloud_src, cloud_dst, info, instance_id):
        image_id = info[COMPUTE][INSTANCES][instance_id]['image_id']
        base_file = "%s/%s" % (cloud_dst[CLOUD][TEMP], "temp%s_base" % instance_id)
        diff_file = "%s/%s" % (cloud_dst[CLOUD][TEMP], "temp%s" % instance_id)
        info[COMPUTE][INSTANCES][instance_id][DIFF][PATH_DST] = diff_file
        convertor = convert_image_to_file.ConvertImageToFile()
        convertor(cfg=cfg,
                  cloud_src=cloud_src,
                  cloud_dst=cloud_dst,
                  image_id=image_id,
                  base_file_name=base_file)
        transporter = transport_file_to_file_via_ssh.TransportFileToFileViaSsh()
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=utl.COMPUTE_RESOURCE,
                        resource_name=utl.INSTANCES_TYPE,
                        resources_root_name=utl.DIFF_BODY)
        self.rebase_diff_file(cloud_dst[CLOUD]['host'], base_file, diff_file)
        self.commit_diff_file(cloud_dst[CLOUD]['host'], diff_file)
        converter = convert_file_to_image.ConvertFileToImage()
        self.convert_to_raw(cloud_dst[CLOUD]['host'], diff_file)
        dst_image_id = converter.run(cfg=cloud_dst.config[CLOUD],
                                     file_path=diff_file,
                                     image_format='raw',
                                     image_name="%s-image" % instance_id)
        info[COMPUTE][INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = dst_image_id

    def start_instance(self, cloud_dst, info, instance_id):
        instance_dst_id = info[COMPUTE][INSTANCES][instance_id]['meta']['dst_id']
        cloud_dst.resources[COMPUTE].change_status('active', instance_id=instance_dst_id)

    def transport_image(self, cfg, cloud_src, cloud_dst, info, instance_id):
        transporter = transport_ceph_to_file_via_ssh.TransportCephToFileViaSsh()
        path_dst = "%s/%s" % (cloud_dst[CLOUD][TEMP], "temp%s" % instance_id)
        info[COMPUTE][INSTANCES][instance_id][DIFF][PATH_DST] = path_dst
        transporter.run(cfg=cfg,
                        cloud_src=cloud_src,
                        cloud_dst=cloud_dst,
                        info=info,
                        resource_type=utl.COMPUTE_RESOURCE,
                        resource_name=utl.INSTANCES_TYPE,
                        resource_root_name=utl.DIFF_BODY)
        converter = convert_file_to_image.ConvertFileToImage()
        dst_image_id = converter.run(cfg=cloud_dst.config[CLOUD],
                                     file_path=path_dst,
                                     image_format='raw',
                                     image_name="%s-image" % instance_id)
        info[COMPUTE][INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = dst_image_id

    def convert_file_to_raw(self, host, filepath):
        with settings(host_string=host):
            with forward_agent(env.key_filename):
                run("qemu-img convert -f %s -O raw %s %s.tmp" %
                    (filepath, filepath, 'qcow'))
                run("cd %s && mv -f %s.tmp %s" % (filepath, filepath))

    def rebase_diff_file(self, host, base_file, diff_file):
        cmd = "qemu-img rebase -u -b %s %s" % (base_file, diff_file)
        with settings(host_string=host):
            run(cmd)

    def commit_diff_file(self, host, diff_file):
        with settings(host_string='host'):
            run("qemu-img commit %s" % diff_file)        
