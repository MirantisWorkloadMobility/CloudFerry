import argparse
import time

import generate_load as old
import real_env_conf

old.config = real_env_conf
NOVA_CLIENT_VERSION = real_env_conf.NOVA_CLIENT_VERSION
GLANCE_CLIENT_VERSION = real_env_conf.GLANCE_CLIENT_VERSION
NEUTRON_CLIENT_VERSION = real_env_conf.NEUTRON_CLIENT_VERSION
CINDER_CLIENT_VERSION = real_env_conf.CINDER_CLIENT_VERSION


class Prerequisites(old.Prerequisites):
    @staticmethod
    def update_vm_status():
        src_cloud = Prerequisites(cloud_prefix='SRC')
        src_vms = [x.__dict__ for x in
                   src_cloud.novaclient.servers.list(
                       search_opts={'all_tenants': 1})]
        return src_vms

    def create_keypairs(self):
        try:
            for user, keypair in zip(real_env_conf.users, real_env_conf.keypairs):
                if user['enabled'] is True:
                    self.switch_user(user=user['name'], password=user['password'],
                                     tenant=user['tenant'])
                    self.novaclient.keypairs.create(**keypair)
            self.switch_user(user=self.username, password=self.password,
                             tenant=self.tenant)
        except Exception as e:
            print "Keypair failed to create:\n %s" % (repr(e))

    def create_vms(self):
        for vm in real_env_conf.vms:
            vm['image'] = self.get_image_id(vm['image'])
            vm['flavor'] = self.get_flavor_id(vm['flavor'])
            vm['nics'] = [{'net-id': self.get_net_id(real_env_conf.networks[0]['name'])}]
            self.check_vm_state(self.novaclient.servers.create(**vm))
        ext_net_id = self.get_net_id(real_env_conf.ext_net['name'])
        port_id = None
        port_list = self.neutronclient.list_ports()
        for vm in real_env_conf.vms:
            for port in port_list.values()[0]:
                vm_id = self.get_vm_id(vm['name'])
                if vm_id == port['device_id']:
                    port_id = port['id']
            floating_id = self.neutronclient.create_floatingip(
                {"floatingip": {"floating_network_id": ext_net_id}})
            floating_id = floating_id['floatingip']['id']
            self.neutronclient.update_floatingip(
                floating_id, {'floatingip': {'port_id': port_id}})
        src_vms = self.update_vm_status()
        net_name = real_env_conf.networks[0]['name']
        for vm in src_vms:
            index = src_vms.index(vm)
            vm_addresses = vm['addresses'][net_name]
            while len(vm_addresses) != 2:
                time.sleep(5)
                src_vms_2 = self.update_vm_status()
                vm_addresses = src_vms_2[index]['addresses'][net_name]
        self.switch_user(user=self.username, password=self.password,
                         tenant=self.tenant)

    def create_networks(self, network_list, subnet_list):
        for network, subnet in zip(network_list, subnet_list):
            if network['name'] == 'mynetwork1':
                net = self.neutronclient.create_network({'network': network})
                subnet['network_id'] = net['network']['id']
                self.neutronclient.create_subnet({'subnet': subnet})

    def create_all_networking(self):
        self.create_networks(real_env_conf.networks, real_env_conf.subnets)
        self.create_router(real_env_conf.routers)
        subnet = None
        for net in self.neutronclient.list_networks()['networks']:
            if net['name'] == 'mynetwork1':
                subnet = net['subnets'][0]
        self.neutronclient.add_interface_router(self.get_router_id(
            real_env_conf.routers[0]['router']['name']), {"subnet_id": subnet})

    def create_security_groups(self):
        for sec_grp in real_env_conf.security_groups:
            self.create_security_group(sec_grp['security_groups'])

    def create_cinder_volumes(self, volumes_list):
        for volume in volumes_list:
            vlm = self.cinderclient.volumes.create(display_name=volume['name'],
                                                   size=volume['size'])
            self.wait_for_volume(volume['name'])
            if 'server_to_attach' in volume:
                self.novaclient.volumes.create_server_volume(
                    server_id=self.get_vm_id(volume['server_to_attach']),
                    volume_id=vlm.id,
                    device=volume['device'])
            self.wait_for_volume(volume['name'])
            vms = self.update_vm_status()
            inst_name = None
            for vol in real_env_conf.cinder_volumes:
                if 'server_to_attach' in vol.keys():
                    inst_name = vol['server_to_attach']
            for vm in vms:
                if vm['name'] == inst_name:
                    index = vms.index(vm)
                    while vms[index]['status'] != 'ACTIVE':
                        time.sleep(5)
                        vms = self.update_vm_status()

    def create_cinder_objects(self):
        self.create_cinder_volumes(real_env_conf.cinder_volumes)
        self.create_cinder_snapshots(real_env_conf.cinder_snapshots)
        self.cinderclient.volume_snapshots.list()

    def emulate_vm_states(self):
        for vm_state in real_env_conf.vm_states:
            # # emulate error state:
            # if vm_state['state'] == u'error':
            #     self.novaclient.servers.reset_state(
            #         server=self.get_vm_id(vm_state['name']),
            #         state=vm_state['state'])
            # emulate suspend state:
            if vm_state['state'] == u'suspend':
                self.novaclient.servers.suspend(self.get_vm_id(vm_state['name']))
            # emulate resize state:
            elif vm_state['state'] == u'pause':
                self.novaclient.servers.pause(self.get_vm_id(vm_state['name']))
            # emulate stop/shutoff state:
            elif vm_state['state'] == u'stop':
                self.novaclient.servers.stop(self.get_vm_id(vm_state['name']))
            # emulate resize state:
            elif vm_state['state'] == u'resize':
                self.novaclient.servers.resize(self.get_vm_id(vm_state['name']),
                                               '2')

    def run_preparation_scenario(self):
        self.create_keypairs()
        self.upload_image()
        self.create_all_networking()
        self.create_vms()
        self.create_vm_snapshots()
        self.create_security_groups()
        self.create_cinder_objects()
        self.emulate_vm_states()
        self.generate_vm_state_list()

    def clean_objects(self):
        try:
            for user, keypair in zip(real_env_conf.users, real_env_conf.keypairs):
                if user['enabled'] is True:
                    self.switch_user(user=user['name'], password=user['password'],
                                     tenant=user['tenant'])
                    self.novaclient.keypairs.delete(keypair['name'])
        except Exception as e:
            print "Keypair failed to delete:\n %s" % (repr(e))
        vms = real_env_conf.vms
        for vm in vms:
            try:
                self.novaclient.servers.delete(self.get_vm_id(vm['name']))
            except Exception as e:
                print "VM %s failed to delete: %s" % (vm['name'], repr(e))
        for image in real_env_conf.images:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(image['name']))
            except Exception as e:
                print "Image %s failed to delete: %s" % (image['name'],
                                                         repr(e))
        nets = real_env_conf.networks
        floatingips = self.neutronclient.list_floatingips()['floatingips']
        for ip in floatingips:
            try:
                self.neutronclient.delete_floatingip(ip['id'])
            except Exception as e:
                print "Ip %s failed to delete: %s" % (
                    ip['floating_ip_address'], repr(e))
        try:
            self.neutronclient.remove_gateway_router(self.get_router_id(real_env_conf.routers))
        except Exception as e:
            print "Failed to remove gateway from router: %s" % repr(e)
        for port in self.neutronclient.list_ports()['ports']:
            try:
                self.neutronclient.remove_interface_router(self.get_router_id(
                    real_env_conf.routers[0]['router']['name']),
                    {'port_id': port['id']})
            except Exception as e:
                print "Port failed to delete: %s" % repr(e)
        for router in real_env_conf.routers:
            try:
                self.neutronclient.delete_router(self.get_router_id(
                    router['router']['name']))
            except Exception as e:
                print "Router failed to delete: %s" % repr(e)
        for network in nets:
            try:
                self.neutronclient.delete_network(self.get_net_id(
                    network['name']))
            except Exception as e:
                print "Network %s failed to delete: %s" % (network['name'],
                                                           repr(e))
        for snapshot in real_env_conf.snapshots:
            try:
                self.glanceclient.images.delete(
                    self.get_image_id(snapshot['image_name']))
            except Exception as e:
                print "Image %s failed to delete: %s" % (
                    snapshot['image_name'], repr(e))
        sgs = self.neutronclient.list_security_groups()['security_groups']
        for sg in sgs:
            try:
                print "delete sg {}".format(sg['name'])
                self.neutronclient.delete_security_group(self.get_sg_id(
                                                         sg['name']))
            except Exception as e:
                print "Security group %s failed to delete: %s" % (sg['name'],
                                                                  repr(e))
        snapshots = real_env_conf.cinder_snapshots
        for snapshot in snapshots:
            try:
                self.cinderclient.volume_snapshots.delete(
                    self.get_volume_snapshot_id(snapshot['display_name']))
            except Exception as e:
                print "Snapshot %s failed to delete: %s" % (
                    snapshot['display_name'], repr(e))
        volumes = real_env_conf.cinder_volumes
        for volume in volumes:
            try:
                self.cinderclient.volumes.delete(
                    self.get_volume_id(volume['name']))
            except Exception as e:
                print "Volume %s failed to delete: %s" % (volume['name'],
                                                          repr(e))


if __name__ == '__main__':
    preqs = Prerequisites()
    parser = argparse.ArgumentParser(
        description='Script to generate load for Openstack and delete '
                    'generated objects')
    parser.add_argument('--clean', help='clean objects described in '
                                        'real_env_conf.ini', action='store_true')
    args = parser.parse_args()
    if args.clean:
        preqs.clean_objects()
    else:
        preqs.run_preparation_scenario()
