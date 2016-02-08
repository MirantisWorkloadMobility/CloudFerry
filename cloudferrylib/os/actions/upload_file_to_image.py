# FIXME code below is not tested functionally. Should be considered dead

from cloudferrylib.base import image
from cloudferrylib.base.action import action
from fabric.api import run, settings
from cloudferrylib.utils import utils as utl

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
FLAVORS = 'flavors'


class UploadFileToImage(action.Action):

    def run(self, info=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        ssh_attempts = self.cloud.cloud_config.migrate.ssh_connection_attempts
        img_res = self.cloud.resources[utl.IMAGE_RESOURCE]

        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            # init
            inst_body = info[INSTANCES][instance_id][utl.INSTANCE_BODY]
            image_id = inst_body['image_id']
            base_file = "/tmp/%s" % ("temp%s_base" % instance_id)
            image_name = "%s-image" % instance_id
            internal_image = img_res.get_image_by_id_converted(image_id)
            images = internal_image[utl.IMAGES_TYPE]
            image_format = images[image_id][utl.IMAGE_BODY]['disk_format']
            if img_res.config.image.convert_to_raw:
                image_format = utl.RAW
            # action
            with settings(host_string=cfg.ssh_host,
                          connection_attempts=ssh_attempts):
                cmd = image.glance_image_create_cmd(cfg, image_name,
                                                    image_format, base_file)
                out = run(cmd)
            image_id = out.split("|")[2].replace(' ', '')
            info[INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = image_id
        return {
            'info': info
        }
