from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl


class ConvertComputeToStorage(action.Action):

    def __init__(self, cloud):
        self.cloud = cloud
        super(ConvertComputeToStorage, self).__init__()

    def run(self, info=None, **kwargs):
        info[utl.STORAGE_RESOURCE] = {utl.VOLUMES_TYPE: {}}
        resource_storage = self.cloud.resources[utl.STORAGE_RESOURCE]
        for instance in info[utl.COMPUTE_RESOURCE][utl.INSTANCES_TYPE].itervalues():
            for v in instance[utl.INSTANCE_BODY]['volumes']:
                volume = resource_storage.read_info(id=v['id'])
                volume[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']]['num_device'] = v['num_device']
                volume[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE][v['id']][utl.META_INFO][utl.INSTANCE_BODY] = \
                    {instance[utl.INSTANCE_BODY]['id']: instance[utl.INSTANCE_BODY]}
                info[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE].update(volume[utl.STORAGE_RESOURCE][utl.VOLUMES_TYPE])
        return {
            'info': info
        }

