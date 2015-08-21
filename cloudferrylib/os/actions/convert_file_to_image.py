
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils
from cloudferrylib.utils import remote_runner


class ConvertFileToImage(action.Action):

    def run(self, file_path=None, image_format=None, image_name=None, **kwargs):
        image_resource = self.cloud.resources[utils.IMAGE_RESOURCE]
        cfg = self.cloud.cloud_config.cloud
        runner = remote_runner.RemoteRunner(cfg.host, cfg.ssh_user)
        return image_resource.glance_img_create(runner, image_name, image_format, file_path)
