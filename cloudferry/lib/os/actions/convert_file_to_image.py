
from cloudferry.lib.base.action import action
from cloudferry.lib.utils import utils


class ConvertFileToImage(action.Action):

    def run(self, file_path=None, img_fmt=None, img_name=None, **kwargs):
        image_resource = self.cloud.resources[utils.IMAGE_RESOURCE]
        return image_resource.glance_img_create(img_name, img_fmt, file_path)
