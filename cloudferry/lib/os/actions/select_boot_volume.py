from cloudferry.lib.base.action import action
import cloudferry.lib.os.actions.utils as utils


class SelectBootVolume(action.Action):

    def run(self, info=None, **kwargs):
        info_boot = utils.select_boot_volume(info)
        return {
            'info': info_boot
        }
