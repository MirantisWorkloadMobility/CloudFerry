
from cloudferrylib.base.action import action
import copy


class ConvertImageToCompute(action.Action):
    def __init__(self, cfg=None):
        self.cfg = cfg
        super(ConvertImageToCompute, self).__init__()

    def run(self, images_info=None, **kwargs):
        images_info = copy.deepcopy(images_info)
        instance_info = {'compute': {'instances': {}}}
        for image in images_info['image']['images'].itervalues():
            if 'instance' not in image['meta']:
                continue
            instance = image['meta']['instance']
            instance['instance']['image_id'] = image['image']['id']
            instance_info['compute']['instances'][instance['instance']['id']] = instance
        return {'info': instance_info}

