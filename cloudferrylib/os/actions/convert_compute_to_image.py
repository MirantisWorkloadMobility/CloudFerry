from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


def get_boot_volume(info):
    pass


def get_image_from_volume(volume):
    pass


class ConvertComputeToImage(action.Action):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, info_compute=None, **kwargs):
        image_info = {}
        image_resource = cloud_src.resources[utl.IMAGE_RESOURCE]
        for instance in info_compute['compute']['instances'].itervalues():
            if instance['instance']['image_id'] is None:
                if instance['instance']['volumes']:
                    volume = get_boot_volume(info_compute)
                    image_id = get_image_from_volume(volume)
            else:
                image_id = instance['instance']['image_id']
            image_info.update(image_resource.read_info(image_id=image_id))
            #TODO instance -> instances
            image_info['image']['images'][image_id]['meta']['instance'] = instance
        return image_info
