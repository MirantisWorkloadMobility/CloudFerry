from Snapshot import *
from SnapshotInstances import SnapshotInstances
from SnapshotImages import SnapshotImages
from SnapshotVolumes import SnapshotVolumes
from SnapshotState import SnapshotState
__author__ = 'mirrorcoder'

# TODO: add creating snapshot of openstack service (glance, cinder, nova(instance, network), network)


class SnapshotStateOpenStack(SnapshotState):

    #TODO: list security groups
    #TODO: list users
    #TODO: list tenants
    def __init__(self, cloud, config_snapshots=[SnapshotInstances, SnapshotVolumes, SnapshotImages]):
        super(SnapshotStateOpenStack, self).__init__(cloud, config_snapshots)

    def create_snapshot(self):
        snapshot = Snapshot()
        for snapshot_class in self.config_snapshots:
            snapshot.union(snapshot_class.create_snapshot())
        return snapshot
