
from cloudferrylib.base.action import action


class ConvertImageToCompute(action.Action):

    def run(self, cfg=None, cloud_src=None, cloud_dst=None, info=None, **kwargs):
        instance_info = {'compute': {'instances': {}}}
        for image in info['image']['images'].itervalues():
            if 'instance' not in image['meta']:
                continue
            instance = image['meta']['instance']
            instance['image_id'] = image['image']['id']
            instance_info['compute']['instances'][instance['id']] = instance
        return instance_info

