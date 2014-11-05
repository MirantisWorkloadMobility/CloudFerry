from cloudferrylib.base.action import action
from cloudferrylib.os.actions import transport_ceph_to_ceph_via_ssh
from cloudferrylib.os.actions import transport_ceph_to_file_via_ssh
from cloudferrylib.os.actions import transport_file_to_ceph_via_ssh
from cloudferrylib.os.actions import transport_file_to_file_via_ssh
from cloudferrylib.os.actions import convert_file_to_image
from cloudferrylib.utils import utils as utl

TRANSPORTER_MAP = {True: {True: transport_ceph_to_ceph_via_ssh.TransportCephToCephViaSsh(),
                          False: transport_ceph_to_file_via_ssh.TransportCephToFileViaSsh},
                   False: {True: transport_file_to_ceph_via_ssh.TransportFileToCephViaSsh(),
                           False: transport_file_to_file_via_ssh.TransportFileToFileViaSsh()}}

CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
COMPUTE = 'compute'
INSTANCES = 'instances'
INSTANCE = 'instance'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
PATH_DST = 'path_dst'
TEMP = 'temp'




class TransportInstance(action.Action):
    #TODO constants
    def run(self, cfg=None, cloud_src=None, cloud_dst=None, info=None, **kwargs):
        is_src_ceph = cloud_src.config[CLOUD][BACKEND].lower() == CEPH
        is_dst_ceph = cloud_dst.config[CLOUD][BACKEND].lower() == CEPH
        instance_id = info[COMPUTE][INSTANCES].iterkeys().next()

        # TODO if has no image?
        if is_src_ceph:
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
            image_id = converter.run(cfg=cloud_dst.config[CLOUD],
                                     file_path=path_dst,
                                     image_format='raw',
                                     image_name="%s-image" % instance_id)
            info[COMPUTE][INSTANCES][instance_id][INSTANCE]['image_id'] = image_id
        else:
            # TODO
            pass
        dst_compute = cloud_dst[COMPUTE]
        dst_compute.deploy(info)

        instance_new_id = info[COMPUTE][INSTANCES][instance_id]['meta']['new_id']

        dst_info = dst_compute.read_info(search_opts={'id': instance_new_id})
        dst_compute.change_status('stop', instance_id=instance_id)

        ephemeral_path_dst = dst_info[COMPUTE][INSTANCES][instance_new_id][EPHEMERAL]['path_src']
        info[COMPUTE][INSTANCES][instance_id][EPHEMERAL][PATH_DST] = ephemeral_path_dst

        diff_path_dst = dst_info[COMPUTE][INSTANCES][instance_new_id][DIFF]['path_src']
        info[COMPUTE][INSTANCES][instance_id][DIFF][PATH_DST] = diff_path_dst

        if not is_src_ceph and not is_dst_ceph:
            transporter = TRANSPORTER_MAP[is_src_ceph][is_dst_ceph]
            transporter.run(cfg=cfg,
                            cloud_src=cloud_src,
                            cloud_dst=cloud_dst,
                            info=info,
                            resource_type=utl.COMPUTE_RESOURCE,
                            resource_name=utl.INSTANCES_TYPE,
                            resource_root_name=utl.DIFF_BODY)

        is_ephemeral = info[COMPUTE][INSTANCES][instance_id][INSTANCE]['is_ephemeral']

        if is_ephemeral:
            transporter = TRANSPORTER_MAP[is_src_ceph][is_dst_ceph]
            transporter.run(cfg=cfg,
                            cloud_src=cloud_src,
                            cloud_dst=cloud_dst,
                            info=info,
                            resource_type=utl.COMPUTE_RESOURCE,
                            resource_name=utl.INSTANCES_TYPE,
                            resource_root_name=utl.EPHEMERAL_BODY)






