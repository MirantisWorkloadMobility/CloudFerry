import unittest

from generate_load import Prerequisites


class VmMigration(unittest.TestCase):

    def setUp(self):
        self.src_cloud = Prerequisites(cloud_prefix='SRC')
        self.dst_cloud = Prerequisites(cloud_prefix='DST')
        self.src_vms = [x.__dict__ for x in
                        self.src_cloud.novaclient.servers.list()]
        self.dst_vms = [x.__dict__ for x in
                        self.dst_cloud.novaclient.servers.list()]
        self.dst_vm_indexes = []
        for src_vm in self.src_vms:
            self.dst_vm_indexes.append([x['name'] for x in self.dst_vms].index(
                src_vm['name']))

    def test_cold_migrate_vm_state(self):
        for src_vm, vm_index in zip(self.src_vms, self.dst_vm_indexes):
            self.assertTrue(src_vm['status'] == 'SHUTOFF' and
                            self.dst_vms[vm_index]['status'] == 'ACTIVE')

    def test_cold_migrate_vm_ip(self):
        for src_vm, vm_index in zip(self.src_vms, self.dst_vm_indexes):
            for src_net in src_vm['addresses']:
                for src_net_addr, dst_net_addr in zip(src_vm['addresses']
                                                      [src_net],
                                                      self.dst_vms[vm_index]
                                                      ['addresses'][src_net]):
                    self.assertTrue(src_net_addr['addr'] ==
                                    dst_net_addr['addr'])

    def test_cold_migrate_vm_security_groups(self):
        for src_vm, vm_index in zip(self.src_vms, self.dst_vm_indexes):
            dst_sec_group_names = [x['name'] for x in
                                   self.dst_vms[vm_index]['security_groups']]
            for security_group in src_vm['security_groups']:
                self.assertTrue(security_group['name'] in dst_sec_group_names)

    @unittest.skip("Temporarily disabled: image's id changes after migrating")
    def test_cold_migrate_vm_image_id(self):
        for src_vm, vm_index in zip(self.src_vms, self.dst_vm_indexes):
            self.assertTrue(src_vm['image']['id'] ==
                            self.dst_vms[vm_index]['image']['id'])
