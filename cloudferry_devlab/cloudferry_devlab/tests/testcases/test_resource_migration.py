# Copyright (c) 2015 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

import collections
import itertools
import pprint
import unittest

from fabric.api import run, settings
from fabric.network import NetworkError
from nose.plugins.attrib import attr

import cloudferry_devlab.tests.config as config
from cloudferry_devlab.tests import functional_test
from cloudferry_devlab.tests import test_exceptions

NET_NAMES_TO_OMIT = ['tenantnet4_segm_id_cidr1',
                     'tenantnet4_segm_id_cidr2']
SUBNET_NAMES_TO_OMIT = ['segm_id_test_subnet_1',
                        'segm_id_test_subnet_2']
PARAMS_NAMES_TO_OMIT = ['cidr', 'gateway_ip', 'provider:segmentation_id']


class ResourceMigrationTests(functional_test.FunctionalTest):
    """
    Test Case class which includes all resource's migration cases.
    """

    def _is_segm_id_test(self, param, name):
        return param in PARAMS_NAMES_TO_OMIT and (
            name in NET_NAMES_TO_OMIT or name in SUBNET_NAMES_TO_OMIT)

    def validate_resource_parameter_in_dst(self, src_list, dst_list,
                                           resource_name, parameter):
        if not src_list:
            self.skipTest(
                'Nothing to migrate - source resources list is empty')
        name_attr = 'name'
        if resource_name == 'volume':
            name_attr = 'display_name'
        for i in src_list:
            for j in dst_list:
                if getattr(i, name_attr) != getattr(j, name_attr):
                    continue
                if getattr(i, parameter, None) and \
                        getattr(i, parameter) != getattr(j, parameter):
                    msg = 'Parameter {param} for resource {res} with name ' \
                          '{name} are different src: {r1}, dst: {r2}'
                    self.fail(msg.format(
                        param=parameter, res=resource_name,
                        name=getattr(i, name_attr), r1=getattr(i, parameter),
                        r2=getattr(j, parameter)))
                break
            else:
                msg = 'Resource {res} with name {r_name} was not found on dst'
                self.fail(msg.format(res=resource_name,
                                     r_name=getattr(i, name_attr)))

    def validate_neutron_resource_parameter_in_dst(self, src_list, dst_list,
                                                   resource_name='networks',
                                                   parameter='name'):
        if not src_list[resource_name]:
            self.skipTest(
                'Nothing to migrate - source resources list is empty')
        for i in src_list[resource_name]:
            for j in dst_list[resource_name]:
                if i['name'] != j['name']:
                    continue
                if i[parameter] != j[parameter]:
                    if not self._is_segm_id_test(parameter, i['name']):
                        msg = 'Parameter {param} for resource {res}' \
                              ' with name {name} are different' \
                              ' src: {r1}, dst: {r2}'
                        self.fail(msg.format(
                            param=parameter, res=resource_name, name=i['name'],
                            r1=i[parameter], r2=j[parameter]))
                break
            else:
                msg = 'Resource {res} with name {r_name} was not found on dst'
                self.fail(msg.format(res=resource_name, r_name=i['name']))

    def validate_flavor_parameters(self, src_flavors, dst_flavors):
        # Id can be changed, but for now in CloudFerry we moving flavor with
        # its id.
        for param in ['name', 'ram', 'vcpus', 'disk', 'id']:
            self.validate_resource_parameter_in_dst(src_flavors, dst_flavors,
                                                    resource_name='flavor',
                                                    parameter=param)

    def validate_network_name_in_port_lists(self, src_ports, dst_ports):
        dst_net_names = [self.dst_cloud.get_net_name(dst_port['network_id'])
                         for dst_port in dst_ports]
        src_net_names = [self.src_cloud.get_net_name(src_port['network_id'])
                         for src_port in src_ports]
        self.assertTrue(dst_net_names.sort() == src_net_names.sort(),
                        msg="Network ports is not the same. SRC: %s \n DST: %s"
                            % (src_net_names, dst_net_names))

    def test_migrate_keystone_users(self):
        """Validate users were migrated with correct name and email."""
        src_users = self.filter_users()
        dst_users = self.dst_cloud.keystoneclient.users.list()

        for param in ['name', 'email']:
            self.validate_resource_parameter_in_dst(src_users, dst_users,
                                                    resource_name='user',
                                                    parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_keystone_user_tenant_roles(self):
        """Validate user's tenant roles were migrated with correct name."""
        src_users = self.filter_users()
        src_user_names = [user.name for user in src_users]
        dst_users = self.dst_cloud.keystoneclient.users.list()
        least_user_match = False
        for dst_user in dst_users:
            if dst_user.name not in src_user_names:
                continue
            least_user_match = True
            src_user_tnt_roles = self.src_cloud.get_user_tenant_roles(dst_user)
            dst_user_tnt_roles = self.dst_cloud.get_user_tenant_roles(dst_user)
            self.validate_resource_parameter_in_dst(
                src_user_tnt_roles, dst_user_tnt_roles,
                resource_name='user_tenant_role', parameter='name')
        msg = ("Either migration is not initiated or it was not successful for"
               " resource 'USER'.")
        self.assertTrue(least_user_match, msg=msg)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_keystone_roles(self):
        """Validate user's roles were migrated with correct name."""
        src_roles = self.filter_roles()
        dst_roles = self.dst_cloud.keystoneclient.roles.list()

        self.validate_resource_parameter_in_dst(src_roles, dst_roles,
                                                resource_name='role',
                                                parameter='name')

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_keystone_tenants(self):
        """Validate tenants were migrated with correct name and description.
        """
        src_tenants = self.filter_tenants()
        dst_tenants_gen = self.dst_cloud.keystoneclient.tenants.list()
        dst_tenants = [x for x in dst_tenants_gen]

        filtering_data = self.filtering_utils.filter_tenants(src_tenants)
        src_tenants = filtering_data[0]

        for param in ['name', 'description']:
            self.validate_resource_parameter_in_dst(src_tenants, dst_tenants,
                                                    resource_name='tenant',
                                                    parameter=param)

    def test_migrate_nova_keypairs(self):
        """Validate keypairs were migrated with correct name and fingerprint.
        """
        src_keypairs = self.filter_keypairs()
        dst_keypairs = self.dst_cloud.get_users_keypairs()

        for param in ['name', 'fingerprint']:
            self.validate_resource_parameter_in_dst(src_keypairs, dst_keypairs,
                                                    resource_name='keypair',
                                                    parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_nova_public_flavors(self):
        """Validate public flavors with parameters were migrated correct.

        :param name: flavor name
        :param ram: RAM amount set for flavor
        :param vcpus: Virtual CPU's amount
        :param disk: disk size
        :param id: flavor's id"""
        src_flavors = self.filter_flavors()
        dst_flavors = self.dst_cloud.novaclient.flavors.list()

        self.validate_flavor_parameters(src_flavors, dst_flavors)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_nova_private_flavors(self):
        """Validate private flavors with parameters were migrated correct.

        List of parameters is the same as for public flavors.
        """
        src_flavors = self.filter_flavors(filter_only_private=True)
        dst_flavors = self.dst_cloud.novaclient.flavors.list(is_public=False)

        self.validate_flavor_parameters(src_flavors, dst_flavors)

    def test_migrate_nova_security_groups(self):
        """Validate security groups were migrated with correct parameters.

        :param name: name of the security group
        :param description: description of specific security group"""
        src_sec_gr = self.filter_security_groups()
        dst_sec_gr = self.dst_cloud.neutronclient.list_security_groups()
        for param in ['name', 'description']:
            self.validate_neutron_resource_parameter_in_dst(
                src_sec_gr, dst_sec_gr, resource_name='security_groups',
                parameter=param)

    @unittest.skipIf(functional_test.get_option_from_config_ini(
        option='keep_affinity_settings') == 'False',
        'Keep affinity settings disabled in CloudFerry config')
    @attr(migrated_tenant=['tenant1', 'tenant2', 'tenant4'])
    def test_migrate_nova_server_groups(self):
        """Validate server groups were migrated with correct parameters.

        :param name: server group name
        :param members: servers in the current group"""
        def get_members_names(client, sg_groups):
            groups = {}
            for sg_group in sg_groups:
                members_names = [client.servers.get(member).name
                                 for member in sg_group.members]
                groups[sg_group.name] = sorted(members_names)
            return groups

        if self.src_cloud.openstack_release == 'grizzly':
            self.skipTest('Grizzly release does not support server groups')
        src_server_groups = self.src_cloud.get_all_server_groups()
        dst_server_groups = self.dst_cloud.get_all_server_groups()
        self.validate_resource_parameter_in_dst(
            src_server_groups, dst_server_groups,
            resource_name='server_groups',
            parameter='name')
        src_members = get_members_names(self.src_cloud.novaclient,
                                        src_server_groups)
        dst_members = get_members_names(self.dst_cloud.novaclient,
                                        dst_server_groups)
        for group in src_members:
            self.assertListEqual(src_members[group], dst_members[group],
                                 'Members in server group: "{0}" are different'
                                 ': "{1}" and "{2}"'.format(group,
                                                            src_members[group],
                                                            dst_members[group])
                                 )

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_image_members(self):
        """Validate image members were migrated with correct names.
        """
        def member_list_collector(_images, client, auth_client):
            _members = []
            for img in _images:
                members = client.image_members.list(img.id)
                if not members:
                    continue
                mbr_list = []
                for mem in members:
                    mem_name = auth_client.tenants.find(id=mem.member_id).name
                    mbr_list.append(mem_name)
                _members.append({img.name: sorted(mbr_list)})
            return sorted(_members)

        src_images = [img for img in self.src_cloud.glanceclient.images.list()
                      if img.name not in config.images_not_included_in_filter]
        dst_images = [img for img in self.dst_cloud.glanceclient.images.list(
            is_public=None)]

        src_members = member_list_collector(src_images,
                                            self.src_cloud.glanceclient,
                                            self.src_cloud.keystoneclient)
        dst_members = member_list_collector(dst_images,
                                            self.dst_cloud.glanceclient,
                                            self.dst_cloud.keystoneclient)
        for member in src_members:
            self.assertTrue(member in dst_members,
                            msg="Member: %s not in the DST list of image "
                                "members." % member)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_glance_images(self):
        """Validate images were migrated with correct parameters.

        :param name: image name
        :param disk_format: raw, vhd, vmdk, vdi, iso, qcow2, etc
        :param container_format: bare, ovf, ova, etc
        :param size: image size
        :param checksum: MD5 checksum of the image file data"""
        src_images = self.filter_images()
        dst_images_gen = self.dst_cloud.glanceclient.images.list()
        dst_images = [x for x in dst_images_gen]

        filtering_data = self.filtering_utils.filter_images(src_images)
        src_images = filtering_data[0]

        for param in ['name', 'disk_format', 'container_format', 'size',
                      'checksum']:
            self.validate_resource_parameter_in_dst(src_images, dst_images,
                                                    resource_name='image',
                                                    parameter=param)

        exclude_images_with_fields = {'delete_on_dst': True}
        src_images = self.filter_images(exclude_images_with_fields)
        filtering_data = self.filtering_utils.filter_images(src_images)
        src_images = filtering_data[0]
        self.validate_resource_parameter_in_dst(src_images, dst_images,
                                                resource_name='image',
                                                parameter='id')

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_deleted_glance_images_only_once(self):
        """Validate deleted and broken images were migrated to dst only once.

        Scenario:
            1. Get deleted and broken image's ids from src
            2. Get all images from dst
            3. Verify each deleted and broken image has been restored once
        """
        src_vms = self.src_cloud.novaclient.servers.list(
            search_opts={'all_tenants': True})
        src_img_ids = [i.id for i in self.src_cloud.glanceclient.images.list()]
        # getting images, from which vms were spawned, but which do not exist
        # in the glance
        to_restore_img_ids = []
        for vm in src_vms:
            if vm.image and vm.image['id'] not in src_img_ids:
                to_restore_img_ids.append(vm.image['id'])
        # getting 'broken' images (which exist in the glance, but deleted in
        # storage)
        all_images = self.migration_utils.get_all_images_from_config()
        broken_images = [i['name'] for i in all_images if i.get('broken')]
        src_images = self.src_cloud.glanceclient.images.list()
        to_restore_img_ids.extend([image.id for image in src_images
                                  if image.name in broken_images])

        dst_images = [x for x in self.dst_cloud.glanceclient.images.list()]
        restored_dst_images = collections.defaultdict(int)
        for deleted_img_id in set(to_restore_img_ids):
            for dst_image in dst_images:
                if dst_image.name and deleted_img_id in dst_image.name:
                    restored_dst_images[deleted_img_id] += 1
        msg = 'Image "%s" was re-created %s times. '
        error_msg = ''
        for image in restored_dst_images:
            if restored_dst_images[image] > 1:
                error_msg += msg % (image, restored_dst_images[image])
        if error_msg:
            self.fail(error_msg)

    @attr(migrated_tenant=['tenant1', 'tenant2'])
    def test_migrate_glance_image_belongs_to_deleted_tenant(self):
        """Validate images from deleted tenants were migrated to dst admin
        tenant."""
        src_image_names = []

        def get_image_by_name(image_list, img_name):
            for image in image_list:
                if image.name == img_name:
                    return image

        for tenant in config.tenants:
            if tenant.get('deleted') and tenant.get('images'):
                src_image_names.extend([image['name'] for image in
                                        tenant['images']])

        dst_images = [image for image in
                      self.dst_cloud.glanceclient.images.list()]
        dst_image_names = [image.name for image in dst_images]
        dst_tenant_id = self.dst_cloud.get_tenant_id(self.dst_cloud.tenant)

        for image_name in src_image_names:
            self.assertTrue(image_name in dst_image_names,
                            'Image {0} is not in DST image list: {1}'
                            .format(image_name, dst_image_names))
            image = get_image_by_name(dst_images, image_name)
            self.assertEqual(image.owner, dst_tenant_id,
                             'Image owner on dst is {0} instead of {1}'.format(
                                 image.owner, dst_tenant_id))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_glance_images_not_in_filter_did_not_migrate(self):
        """Validate images not in filter weren't migrated."""
        dst_images_gen = self.dst_cloud.glanceclient.images.list()
        dst_images = [x.name for x in dst_images_gen]
        for image in config.images_not_included_in_filter:
            self.assertTrue(image not in dst_images,
                            'Image migrated despite that it was not included '
                            'in filter, Image info: \n{}'.format(image))

    def test_glance_image_deleted_and_migrated_second_time_with_new_id(self):
        src_images = []
        for image in config.images:
            if image.get('delete_on_dst'):
                src_images.append(image)
        dst_images_gen = self.dst_cloud.glanceclient.images.list()
        dst_images = [x for x in dst_images_gen]

        for src_image in src_images:
            src_image = self.src_cloud.glanceclient.images.get(
                src_image['id'])
            for dst_image in dst_images:
                if src_image.name == dst_image.name:
                    self.assertNotEqual(
                        src_image.id,
                        dst_image.id,
                        "The image with name {src_image_name} have the "
                        "same ID on dst - must be different for this image,"
                        "because this image was migrated and deleted on dst. "
                        "On the next migration must be generated new ID".
                        format(src_image_name=src_image.name)
                    )

    def test_migrate_neutron_networks(self):
        """Validate networks were migrated with correct parameters.

        :param name:
        :param provider\\:network_type:
        :param provider\\:segmentation_id:"""
        src_nets = self.filter_networks()
        dst_nets = self.dst_cloud.neutronclient.list_networks()

        for param in ['name', 'provider:network_type',
                      'provider:segmentation_id', 'provider:physical_network']:
            self.validate_neutron_resource_parameter_in_dst(src_nets, dst_nets,
                                                            parameter=param)

    def test_migrate_neutron_subnets(self):
        """Validate subnets were migrated with correct parameters.

        :param name:
        :param gateway_ip:
        :param cidr:
        :param dns_nameservers:"""
        src_subnets = self.filter_subnets()
        dst_subnets = self.dst_cloud.neutronclient.list_subnets()

        for param in ['name', 'gateway_ip', 'cidr', 'dns_nameservers']:
            self.validate_neutron_resource_parameter_in_dst(
                src_subnets, dst_subnets, resource_name='subnets',
                parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_neutron_routers(self):
        """Validate routers were migrated with correct parameters.

        :param name:
        :param external_gateway_info:"""
        def format_external_gateway_info(client, info):
            """ Method replaces network id with network name and deletes all
            attributes except enable_snat and network_name
            """
            _info = {'network_name': client.neutronclient.show_network(
                info['network_id'])['network']['name']}
            if check_snat:
                _info['enable_snat'] = info['enable_snat']
            return _info

        src_routers = self.filter_routers()
        dst_routers = self.dst_cloud.neutronclient.list_routers()
        # check, do src and dst clouds support snat
        check_snat = {self.src_cloud.openstack_release,
                      self.dst_cloud.openstack_release}.issubset({'icehouse',
                                                                  'juno'})
        for src_router in src_routers['routers']:
            src_router['external_gateway_info'] = format_external_gateway_info(
                self.src_cloud, src_router['external_gateway_info'])
        for dst_router in dst_routers['routers']:
            dst_router['external_gateway_info'] = format_external_gateway_info(
                self.dst_cloud, dst_router['external_gateway_info'])
        for param in ['name', 'external_gateway_info']:
            self.validate_neutron_resource_parameter_in_dst(
                src_routers, dst_routers, resource_name='routers',
                parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_validate_router_migrated_once(self):
        """Validate routers were migrated just one time."""
        src_routers_names = [router['name'] for router
                             in self.filter_routers()['routers']]
        dst_routers_names = [router['name'] for router
                             in self.dst_cloud.neutronclient.list_routers()
                             ['routers']]
        for router in src_routers_names:
            self.assertTrue(dst_routers_names.count(router) == 1,
                            msg='Router %s presents multiple times' % router)

    @attr(migrated_tenant=['tenant1', 'tenant2'])
    def test_router_connected_to_correct_networks(self):
        """Validate routers were connected to correct network on dst."""
        src_routers = self.filter_routers()['routers']
        dst_routers = self.dst_cloud.neutronclient.list_routers()['routers']
        for dst_router in dst_routers:
            dst_ports = self.dst_cloud.neutronclient.list_ports(
                retrieve_all=True, **{'device_id': dst_router['id']})['ports']
            for src_router in src_routers:
                if src_router['name'] == dst_router['name']:
                    src_ports = self.src_cloud.neutronclient.list_ports(
                        retrieve_all=True,
                        **{'device_id': src_router['id']})['ports']
                    self.validate_network_name_in_port_lists(
                        src_ports=src_ports, dst_ports=dst_ports)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_router_migrated_to_correct_tenant(self):
        """Validate routers were migrated to correct tenant on dst."""
        src_routers = self.filter_routers()['routers']
        dst_routers = self.dst_cloud.neutronclient.list_routers()['routers']
        for dst_router in dst_routers:
            dst_tenant_name = self.dst_cloud.get_tenant_name(
                dst_router['tenant_id'])
            for src_router in src_routers:
                if src_router['name'] == dst_router['name']:
                    src_tenant_name = self.src_cloud.get_tenant_name(
                        src_router['tenant_id'])
                    self.assertTrue(src_tenant_name == dst_tenant_name,
                                    msg='DST tenant name %s is not equal to '
                                        'SRC %s' %
                                        (dst_tenant_name, src_tenant_name))

    @attr(migrated_tenant='tenant2')
    def test_migrate_vms_parameters(self):
        """Validate VMs were migrated with correct parameters.

        :param name:
        :param config_drive:
        :param key_name:"""
        src_vms = self.filter_vms()
        dst_vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})

        filtering_data = self.filtering_utils.filter_vms(src_vms)
        src_vms = filtering_data[0]

        src_vms = [vm for vm in src_vms if vm.status != 'ERROR']

        for param in ['name', 'config_drive', 'key_name']:
            self.validate_resource_parameter_in_dst(
                src_vms, dst_vms, resource_name='VM', parameter=param)

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_migrate_vms_with_floating(self):
        """Validate VMs were migrated with floating ip assigned."""
        vm_names_with_fip = self.get_vms_with_fip_associated()
        dst_vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        for vm in dst_vms:
            if vm.name not in vm_names_with_fip:
                continue
            for net in vm.addresses.values():
                if [True for addr in net if 'floating' in addr.values()]:
                    break
            else:
                raise RuntimeError('Vm {0} does not have floating ip'.format(
                    vm.name))

    @attr(migrated_tenant='tenant2')
    def test_migrate_cinder_volumes(self):
        """Validate volumes were migrated with correct parameters.

        :param name:
        :param size:
        :param bootable:
        :param metadata:"""
        src_volume_list = self.filter_volumes()
        dst_volume_list = self.dst_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})

        def ignore_default_metadata(volumes):
            default_keys = ('readonly', 'attached_mode', 'src_volume_id')
            for vol in volumes:
                for default_key in default_keys:
                    if default_key in vol.metadata:
                        del vol.metadata[default_key]
            return volumes

        src_volume_list = ignore_default_metadata(src_volume_list)
        dst_volume_list = ignore_default_metadata(dst_volume_list)

        for parameter in ['display_name', 'size', 'bootable', 'metadata']:
            self.validate_resource_parameter_in_dst(
                src_volume_list, dst_volume_list, resource_name='volume',
                parameter=parameter)

        def ignore_image_id(volumes):
            for vol in volumes:
                metadata = getattr(vol, 'volume_image_metadata', None)
                if metadata and 'image_id' in metadata:
                    del metadata['image_id']
                    vol.volume_image_metadata = metadata
            return volumes

        src_volume_list = ignore_image_id(src_volume_list)
        dst_volume_list = ignore_image_id(dst_volume_list)

        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='volume_image_metadata')

    @attr(migrated_tenant='tenant2')
    def test_migrate_cinder_volumes_data(self):
        """Validate volume data was migrated correctly.

        Scenario:
            1. Get volumes on which data was written
            2. Get floating ip address of vm, to which volume attached
            3. Open TCP/22 port for vm's tenant,
            4. Wait until vm accessible via ssh
            5. Check mount point has been migrated with ephemeral storage
            6. Mount volume
            7. Check data on volume is correct
        """
        def check_file_valid(filename):
            get_md5_cmd = 'md5sum %s' % filename
            get_old_md5_cmd = 'cat %s_md5' % filename
            md5sum = self.migration_utils.execute_command_on_vm(
                vm_ip, get_md5_cmd).split()[0]
            old_md5sum = self.migration_utils.execute_command_on_vm(
                vm_ip, get_old_md5_cmd).split()[0]
            if md5sum != old_md5sum:
                msg = "MD5 of file %s before and after migrate is different"
                raise RuntimeError(msg % filename)

        def check_mount_point_exists(ip, vol):
            """ Method check directory, which will used as mount point for
            volume, exists on the vm's ephemeral storage

            :param ip:     vm's ip address, where mount point should be checked

            :param vol:    dict with volume's parameters from tests/config.py
            """
            command = '[ -d %s ]' % vol['mount_point']
            try:
                self.migration_utils.execute_command_on_vm(ip, command)
            except SystemExit:
                msg = ('Mount point for volume "{vol_name}" not found. Check '
                       'directory "{mp}" exists on vm with name "{vm_name}. '
                       'If not exists check ephemeral storage migration works '
                       'properly.')
                self.fail(msg.format(vol_name=vol['display_name'],
                                     mp=vol['mount_point'], vm_name=vm.name))

        volumes = config.cinder_volumes
        volumes += itertools.chain(*[tenant['cinder_volumes'] for tenant
                                     in config.tenants if 'cinder_volumes'
                                     in tenant])
        for volume in volumes:
            attached_volume = volume.get('server_to_attach')
            if not volume.get('write_to_file') or not attached_volume:
                continue
            vm = self.dst_cloud.novaclient.servers.get(
                self.dst_cloud.get_vm_id(volume['server_to_attach']))
            vm_ip = self.migration_utils.get_vm_fip(vm)
            self.migration_utils.open_ssh_port_secgroup(self.dst_cloud,
                                                        vm.tenant_id)
            self.migration_utils.wait_until_vm_accessible_via_ssh(vm_ip)
            check_mount_point_exists(vm_ip, volume)
            cmd = 'mount {0} {1}'.format(volume['device'],
                                         volume['mount_point'])
            self.migration_utils.execute_command_on_vm(vm_ip, cmd,
                                                       warn_only=True)
            for _file in volume['write_to_file']:
                check_file_valid(volume['mount_point'] + _file['filename'])

    def test_cinder_volumes_not_in_filter_did_not_migrate(self):
        """Validate volumes not in filter weren't migrated."""
        src_volume_list = self.filter_volumes()
        dst_volume_list = self.dst_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        dst_volumes = [x.id for x in dst_volume_list]

        filtering_data = self.filtering_utils.filter_volumes(src_volume_list)

        volumes_filtered_out = filtering_data[1]
        for volume in volumes_filtered_out:
            self.assertTrue(volume.id not in dst_volumes,
                            'Volume migrated despite that it was not included '
                            'in filter, Volume info: \n{}'.format(volume))

    def test_invalid_status_cinder_volumes_did_not_migrate(self):
        """Validate volumes with invalid statuses weren't migrated.
        Statuses described in :mod:`config.py`
        """
        src_volume_list = self.src_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        dst_volume_list = self.dst_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        dst_volumes = [x.id for x in dst_volume_list]

        invalid_status_volumes = [
            vol for vol in src_volume_list
            if vol.status in config.INVALID_STATUSES
            ]

        for volume in invalid_status_volumes:
            self.assertTrue(volume.id not in dst_volumes,
                            'Volume migrated despite that it had '
                            'invalid status, Volume info: \n{}'.format(volume))

    @unittest.skip("Temporarily disabled: snapshots doesn't implemented in "
                   "cinder's nfs driver")
    def test_migrate_cinder_snapshots(self):
        """Validate volume snapshots were migrated with correct parameters.

        :param name:
        :param size:"""
        src_volume_list = self.filter_volumes()
        dst_volume_list = self.dst_cloud.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})

        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='display_name')
        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='size')

    def test_migrate_tenant_quotas(self):
        """Validate tenant's quotas were migrated to correct tenant.

        Scenario:
            1. Get nova quota parameters from src cloud
            2. Get neutron quota parameters from src cloud
            3. Get cinder quota parameters, common for src and dst clouds
            4. Get nova, neutron and cinder quotas values for each tenant from
                src cloud
            5. Get nova, neutron and cinder quotas values for each tenant from
                dst cloud
            6. Verify nova tenant quotas the same on dst and src clouds
            7. Verify neutron tenant quotas the same on dst and src clouds
            8. Verify cinder tenant quotas the same on dst and src clouds
        """

        def get_tenant_quotas(tenants, client):
            """
            Method gets nova and neutron quotas for given tenants, and saves
            quotas, which are exist on src (on dst could exists quotas, which
            are not exist on src).
            """
            qs = {}
            for t in tenants:
                qs[t.name] = {'nova_q': {}, 'neutron_q': {}, 'cinder_q': {}}
                nova_quota = client.novaclient.quotas.get(t.id).to_dict()
                for k, v in nova_quota.iteritems():
                    if k in src_nova_quota_keys and k != 'id':
                        qs[t.name]['nova_q'][k] = v
                neutron_quota = client.neutronclient.show_quota(t.id)['quota']
                for k, v in neutron_quota.iteritems():
                    if k in src_neutron_quota_keys:
                        qs[t.name]['neutron_q'][k] = v
                cinder_quota = getattr(client.cinderclient.quotas.get(t.id),
                                       '_info')
                for k, v in cinder_quota.iteritems():
                    if k in cinder_quota_keys and k != 'id':
                        qs[t.name]['cinder_q'][k] = v
            return qs
        src_nova_quota_keys = self.src_cloud.novaclient.quotas.get(
            self.src_cloud.keystoneclient.tenant_id).to_dict().keys()
        src_neutron_quota_keys = self.src_cloud.neutronclient.show_quota(
            self.src_cloud.keystoneclient.tenant_id)['quota'].keys()
        src_cinder_q_keys = getattr(self.src_cloud.cinderclient.quotas.get(
            self.src_cloud.keystoneclient.tenant_id), '_info').keys()
        dst_cinder_q_keys = getattr(self.dst_cloud.cinderclient.quotas.get(
            self.dst_cloud.keystoneclient.tenant_id), '_info').keys()
        cinder_quota_keys = set(src_cinder_q_keys) & set(dst_cinder_q_keys)

        src_quotas = get_tenant_quotas(self.filter_tenants(), self.src_cloud)
        dst_quotas = get_tenant_quotas(
            self.dst_cloud.keystoneclient.tenants.list(), self.dst_cloud)
        for tenant in src_quotas:
            self.assertIn(tenant, dst_quotas,
                          'Tenant %s is missing on dst' % tenant)
            # Check nova quotas
            self.assertDictEqual(
                src_quotas[tenant]['nova_q'], dst_quotas[tenant]['nova_q'],
                'Nova quotas for tenant %s migrated not successfully' % tenant)
            # Check neutron quotas
            self.assertDictEqual(
                src_quotas[tenant]['neutron_q'],
                dst_quotas[tenant]['neutron_q'],
                'Neutron quotas for tenant %s migrated not successfully'
                % tenant)
            # Check cinder quotas
            self.assertDictEqual(
                src_quotas[tenant]['cinder_q'], dst_quotas[tenant]['cinder_q'],
                'Cinder quotas for tenant %s migrated not successfully'
                % tenant)

    @attr(migrated_tenant='tenant2')
    def test_ssh_connectivity_by_keypair(self):
        """Validate migrated VMs ssh connectivity by keypairs."""
        vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        for _vm in vms:
            if 'keypair_test' in _vm.name:
                vm = _vm
                break
        else:
            raise RuntimeError(
                'VM for current test was not spawned on dst. Make sure vm with'
                'name keypair_test has been created on src')
        ip_addr = self.migration_utils.get_vm_fip(vm)
        # make sure 22 port in sec group is open
        self.migration_utils.open_ssh_port_secgroup(self.dst_cloud,
                                                    vm.tenant_id)
        # try to connect to vm via key pair
        with settings(host_string=ip_addr, user="root",
                      key=config.private_key['id_rsa'],
                      abort_on_prompts=True, connection_attempts=3,
                      disable_known_hosts=True):
            try:
                run("pwd", shell=False)
            except NetworkError:
                msg = 'VM with name {name} and ip: {addr} is not accessible'
                self.fail(msg.format(name=vm.name, addr=ip_addr))
            except SystemExit:
                msg = 'VM with name {name} and ip: {addr} is not accessible ' \
                      'via key pair'
                self.fail(msg.format(name=vm.name, addr=ip_addr))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_floating_ips_migrated(self):
        """Validate floating IPs were migrated correctly."""
        def get_fips(client):
            return set([fip['floating_ip_address']
                        for fip in client.list_floatingips()['floatingips']])

        src_fips = self.filter_floatingips()
        dst_fips = get_fips(self.dst_cloud.neutronclient)

        missing_fips = src_fips - dst_fips

        if missing_fips:
            self.fail("{num} floating IPs did not migrate to destination: "
                      "{fips}".format(num=len(missing_fips),
                                      fips=pprint.pformat(missing_fips)))

    @unittest.skipIf(functional_test.get_option_from_config_ini(
        option='change_router_ips') == 'False',
        'Change router ips disabled in CloudFerry config')
    def test_ext_router_ip_changed(self):
        """Validate router IPs were changed after migration."""
        dst_routers = self.dst_cloud.get_ext_routers()
        src_routers = self.src_cloud.get_ext_routers()
        for dst_router in dst_routers:
            for src_router in src_routers:
                if dst_router['name'] != src_router['name']:
                    continue
                src_gateway = self.src_cloud.neutronclient.list_ports(
                    device_id=src_router['id'],
                    device_owner='network:router_gateway')['ports'][0]
                dst_gateway = self.dst_cloud.neutronclient.list_ports(
                    device_id=dst_router['id'],
                    device_owner='network:router_gateway')['ports'][0]
                self.assertNotEqual(
                    src_gateway['fixed_ips'][0]['ip_address'],
                    dst_gateway['fixed_ips'][0]['ip_address'],
                    'GW ip addresses of router "{0}" are same on src and dst:'
                    ' {1}'.format(dst_router['name'],
                                  dst_gateway['fixed_ips'][0]['ip_address']))

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_not_valid_vms_did_not_migrate(self):
        """Validate VMs with invalid statuses weren't migrated.
        Invalid VMs have 'broken': True value in :mod:`config.py`
        """
        all_vms = self.migration_utils.get_all_vms_from_config()
        vms = [vm['name'] for vm in all_vms if vm.get('broken')]
        migrated_vms = []
        for vm in vms:
            try:
                self.dst_cloud.get_vm_id(vm)
                migrated_vms.append(vm)
            except test_exceptions.NotFound:
                pass
        if migrated_vms:
            self.fail('Not valid vms %s migrated')

    @attr(migrated_tenant=['admin', 'tenant1', 'tenant2'])
    def test_not_valid_images_did_not_migrate(self):
        """Validate images with invalid statuses weren't migrated.
        Invalid images have 'broken': True value in :mod:`config.py`
        """
        all_images = self.migration_utils.get_all_images_from_config()
        images = [image['name'] for image in all_images if image.get('broken')]
        migrated_images = []
        for image in images:
            try:
                self.dst_cloud.get_image_id(image)
                migrated_images.append(image)
            except test_exceptions.NotFound:
                pass
        if migrated_images:
            self.fail('Not valid images %s migrated')

    def test_migrate_lbaas_pools(self):
        """Validate load balancer pools were migrated successfuly."""
        src_lb_pools = self.replace_id_with_name(
            self.src_cloud, 'pools', self.filter_pools())
        dst_lb_pools = self.replace_id_with_name(
            self.dst_cloud, 'pools', self.dst_cloud.neutronclient.list_pools())

        for param in ['tenant_name', 'subnet_name', 'protocol', 'lb_method']:
            self.validate_neutron_resource_parameter_in_dst(
                src_lb_pools, dst_lb_pools, resource_name='pools',
                parameter=param)

    def test_migrate_lbaas_monitors(self):
        """Validate load balancer monitors were migrated successfuly."""
        monitors = self.filter_health_monitors()
        src_lb_monitors = self.replace_id_with_name(
            self.src_cloud, 'health_monitors', monitors)
        monitors = self.dst_cloud.neutronclient.list_health_monitors()
        dst_lb_monitors = self.replace_id_with_name(
            self.dst_cloud, 'health_monitors', monitors)
        parameters_to_validate = ['type', 'delay', 'timeout', 'max_retries',
                                  'tenant_name']

        src_lb_monitors = self.filter_resource_parameters(
            'health_monitors', src_lb_monitors, parameters_to_validate)
        dst_lb_monitors = self.filter_resource_parameters(
            'health_monitors', dst_lb_monitors, parameters_to_validate)
        self.assertListEqual(sorted(src_lb_monitors['health_monitors']),
                             sorted(dst_lb_monitors['health_monitors']))

    def test_migrate_lbaas_members(self):
        """Validate load balancer members were migrated successfuly."""
        members = self.filter_lbaas_members()
        src_lb_members = self.replace_id_with_name(
            self.src_cloud, 'members', members)
        members = self.dst_cloud.neutronclient.list_members()
        dst_lb_members = self.replace_id_with_name(
            self.dst_cloud, 'members', members)
        params_to_validate = ['protocol_port', 'address', 'pool_name',
                              'tenant_name']

        src_lb_members = self.filter_resource_parameters(
            'members', src_lb_members, params_to_validate)
        dst_lb_members = self.filter_resource_parameters(
            'members', dst_lb_members, params_to_validate)
        self.assertListEqual(sorted(src_lb_members['members']),
                             sorted(dst_lb_members['members']))

    def test_migrate_lbaas_vips(self):
        """Validate load balancer vips were migrated successfuly."""
        vips = self.filter_vips()
        src_lb_vips = self.replace_id_with_name(self.src_cloud, 'vips', vips)
        vips = self.dst_cloud.neutronclient.list_vips()
        dst_lb_vips = self.replace_id_with_name(self.dst_cloud, 'vips', vips)
        for param in ['description', 'address', 'protocol', 'protocol_port',
                      'connection_limit', 'pool_name', 'tenant_name',
                      'subnet_name']:
            self.validate_neutron_resource_parameter_in_dst(
                src_lb_vips, dst_lb_vips, resource_name='vips',
                parameter=param)

    def test_lbaas_pools_belong_deleted_tenant_not_migrate(self):
        """Validate load balancer pools in deleted tenant weren't migrated."""
        pools = []
        for tenant in config.tenants:
            if not tenant.get('deleted'):
                continue
            if tenant.get('pools'):
                pools.extend(tenant['pools'])
        pools_names = {pool['name'] for pool in pools}
        dst_pools = self.dst_cloud.neutronclient.list_pools()['pools']
        dst_pools_names = {dst_pool['name'] for dst_pool in dst_pools}
        migrated_pools = dst_pools_names.intersection(pools_names)
        if migrated_pools:
            msg = 'Lbaas pools %s belong to deleted tenant and were migrated'
            self.fail(msg % list(migrated_pools))

    @staticmethod
    def filter_resource_parameters(resource, res_list, param_list):
        finals_res_list = {resource: []}
        for res in res_list[resource]:
            finals_res_list[resource].append(
                {param: res[param] for param in res if param in param_list})
        return finals_res_list

    @staticmethod
    def replace_id_with_name(client, resource, res_list):
        for res in res_list[resource]:
            if res.get('pool_id'):
                res['pool_name'] = client.neutronclient.show_pool(
                    res['pool_id'])['pool']['name']
            if res.get('subnet_id'):
                res['subnet_name'] = client.neutronclient.show_subnet(
                    res['subnet_id'])['subnet']['name']
            if res.get('tenant_id'):
                res['tenant_name'] = client.keystoneclient.tenants.get(
                    res['tenant_id']).name
        return res_list
