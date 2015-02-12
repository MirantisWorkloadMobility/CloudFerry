from fabric.api import run, settings, env
from cloudferrylib.base.action import action
from cloudferrylib.utils import forward_agent
from cloudferrylib.utils import utils as utl

INSTANCES = 'instances'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
DIFF_OLD = 'diff_old'
EPHEMERAL_OLD = 'ephemeral_old'
PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
HOST_SRC = 'host_src'


class LoadComputeImageToFile(action.Action):
    def run(self, info=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            image_id = info[INSTANCES][instance_id][utl.INSTANCE_BODY]['image_id']
            base_file = "%s/%s" % (self.cloud.cloud_config.cloud.temp, "temp%s_base" % instance_id)
            diff_file = "%s/%s" % (self.dst_cloud.cloud_config.cloud.temp, "temp%s" % instance_id)
            with settings(host_string=cfg.host):
                with forward_agent(env.key_filename):
                    run(("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                         "--os-auth-url=http://%s:35357/v2.0 " +
                        "image-download %s > %s") %
                        (cfg.user,
                         cfg.password,
                         cfg.tenant,
                         cfg.host,
                         image_id,
                         base_file))
            instance[DIFF][PATH_DST] = diff_file
            instance[DIFF][HOST_DST] = self.dst_cloud.getIpSsh()
        return {
            'info': info
        }