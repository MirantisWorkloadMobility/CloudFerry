from migrationlib.os.osCommon import osCommon
from Snapshot import Snapshot

__author__ = 'mirrorcoder'

# TODO: add creating snapshot of openstack service (glance, cinder, nova(instance, network), network)


class SnapshotStateOpenStack(osCommon):

    def __init__(self, config):
        """ config initialization"""
        self.config = config
        self.snapshots = []
        super(SnapshotStateOpenStack, self).__init__(self.config)

    def create_snapshot(self):
        return Snapshot()

    def diff_snapshot(self, snapshot_one=None, snapshot_two=None):
        return Snapshot()
