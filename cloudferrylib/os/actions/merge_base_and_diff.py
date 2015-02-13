from fabric.api import run, settings, env
from cloudferrylib.base.action import action
from cloudferrylib.utils import forward_agent
from cloudferrylib.utils import utils as utl

INSTANCES = 'instances'


class MergeBaseDiff(action.Action):
    def run(self, info=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            host = cfg.host
            base_file = "%s/%s" % (cfg.temp, "temp%s_base" % instance_id)
            diff_file = "%s/%s" % (cfg.temp, "temp%s" % instance_id)
            self.rebase_diff_file(host, base_file, diff_file)
            self.commit_diff_file(host, diff_file)

    def rebase_diff_file(self, host, base_file, diff_file):
        cmd = "qemu-img rebase -u -b %s %s" % (base_file, diff_file)
        with settings(host_string=host):
            run(cmd)

    def commit_diff_file(self, host, diff_file):
        with settings(host_string=host):
            run("qemu-img commit %s" % diff_file)