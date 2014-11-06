from cloudferrylib.base.action import action
import utils


class SelectBootVolume(action.Action):

    def __init__(self, cloud):
        self.cloud = cloud
        super(SelectBootVolume, self).__init__()

    def run(self, info=None, **kwargs):
        info_boot = utils.select_boot_volume(info)
        return {
            'info': info_boot
        }

