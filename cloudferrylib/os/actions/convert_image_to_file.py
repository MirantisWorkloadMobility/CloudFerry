from fabric.api import run, settings, env
from cloudferrylib.base import image
from cloudferrylib.base.action import action
from cloudferrylib.utils import forward_agent


class ConvertImageToFile(action.Action):

    def run(self, image_id=None, base_filename=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        with settings(host_string=cfg.host):
            with forward_agent(env.key_filename):
                cmd = image.glance_image_download_cmd(cfg, image_id,
                                                      base_filename)
                run(cmd)
