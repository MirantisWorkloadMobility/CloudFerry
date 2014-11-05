from cloudferrylib.base.action import action


class ConvertComputeToImage(action.Action):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, info_compute=None, **kwargs):
        image_info = {}
        for instance in info_compute['compute']['instances'].itervalues():
            if instance['instance']['image_id'] is None:
                return
            image_resource = cloud_src['image']
            image_id = instance['instance']['image_id']
            image_info.update(image_resource.read_info(image_id=image_id))
            #TODO instance -> instances
            image_info['image']['images'][image_id]['meta']['instance'] = instance
        return image_info

