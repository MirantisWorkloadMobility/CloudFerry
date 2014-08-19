from Snapshot import *

__author__ = 'mirrorcoder'

# TODO: add creating snapshot of openstack service (glance, cinder, nova(instance, network), network)


class SnapshotStateOpenStack:

    def __init__(self, cloud):
        self.keystone_client = cloud.keystone_client
        self.nova_client = cloud.nova_client
        self.cinder_client = cloud.cinder_client
        self.network_client = cloud.network_client
        self.glance_client = cloud.glance_client
        self.keystone_db_conn_url = cloud.keystone_client

    def create_snapshot(self):
        snapshot = Snapshot()
        [snapshot.addInstance(id=instance.id,
                              status=instance.status,
                              name=instance.name)
         for instance in self.nova_client.servers.list()]
        [snapshot.addImage(id=image.id,
                           disk_format=image.disk_format,
                           name=image.name,
                           checksum=image.checksum)
         for image in self.glance_client.images.list()]
        [snapshot.addVolume(id=volume.id,
                            status=volume.status,
                            display_name=volume.display_name,
                            attachments=volume.attachments)
         for volume in self.cinder_client.volumes.list()]
        #TODO: list security groups
        #TODO: list users
        #TODO: list tenants
        return snapshot

    @staticmethod
    def diff_snapshot(snapshot_one, snapshot_two):
        snapshot_one_res = snapshot_one.convert_to_dict()
        snapshot_two_res = snapshot_two.convert_to_dict()
        snapshot_diff = Snapshot()
        for item_two in snapshot_two_res:
            for obj in snapshot_two_res[item_two]:
                if not obj in snapshot_one_res[item_two]:
                    snapshot_diff.add(obj, item_two, DiffObject(ADD, snapshot_two_res[item_two][obj]))
                elif snapshot_two_res[item_two][obj] != snapshot_one_res[item_two][obj]:
                    snapshot_diff.add(obj, item_two, DiffObject(CHANGE,
                                                                DiffValue(snapshot_one_res[item_two][obj],
                                                                          snapshot_two_res[item_two][obj])))
            for obj in snapshot_one_res[item_two]:
                if not obj in snapshot_two_res[item_two]:
                    snapshot_diff.add(obj, item_two, DiffObject(DELETE, snapshot_one_res[item_two][obj]))
        return snapshot_diff
