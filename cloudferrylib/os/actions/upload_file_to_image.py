
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
        img_res = self.cloud.resources[utl.IMAGE_RESOURCE]
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            # init
            image_id = info[INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id']
            base_file = "%s/%s" % (self.cloud.cloud_config.cloud.temp, "temp%s_base" % instance_id)
            image_name = "%s-image" % instance_id
            images = img_res.read_info(image_id=image_id)[utl.IMAGES_TYPE]
            image_format = images[image_id][utl.IMAGE_BODY]['disk_format']
            if img_res.config.image.convert_to_raw:
                image_format = utl.RAW
            # action
            with settings(host_string=cfg.host):
                out = run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                           "--os-auth-url=%s " +
                           "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                           "grep id") %
                          (cfg.user,
                           cfg.password,
                           cfg.tenant,
                           cfg.auth_url,
                           image_name,
                           image_format,
                           base_file))
            image_id = out.split("|")[2].replace(' ', '')
            info[INSTANCES][instance_id][INSTANCE_BODY]['image_id'] = image_id
        return {
            'info': info
        }
