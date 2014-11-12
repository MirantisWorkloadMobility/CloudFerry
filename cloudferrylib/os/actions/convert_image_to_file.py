from fabric.api import run, settings, env
from cloudferrylib.base.action import action
from cloudferrylib.utils import forward_agent


class ConvertImageToFile(action.Action):

    def __init__(self, cloud=None):
        self.cloud = cloud
        super(ConvertImageToFile, self).__init__()

    def run(self, image_id=None, base_filename=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
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
                     base_filename))

