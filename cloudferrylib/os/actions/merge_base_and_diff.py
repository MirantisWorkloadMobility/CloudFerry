from fabric.api import run, settings, env
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils as utl

INSTANCES = 'instances'


class MergeBaseDiff(action.Action):
    def run(self, info=None, **kwargs):
        cfg = self.cloud.cloud_config.cloud
        for instance_id, instance in info[utl.INSTANCES_TYPE].iteritems():
            base_file = "%s/%s" % (cfg.temp, "temp%s_base" % instance_id)
            diff_file = "%s/%s" % (cfg.temp, "temp%s" % instance_id)
            self.rebase_diff_file(cfg.ssh_host, base_file, diff_file)
            self.commit_diff_file(cfg.ssh_host, diff_file)

    @staticmethod
    def rebase_diff_file(host, base_file, diff_file):
        cmd = "qemu-img rebase -u -b %s %s" % (base_file, diff_file)
        with settings(host_string=host,
                      connection_attempts=env.connection_attempts):
            run(cmd)

    @staticmethod
    def commit_diff_file(host, diff_file):
        with settings(host_string=host,
                      connection_attempts=env.connection_attempts):
            run("qemu-img commit %s" % diff_file)
