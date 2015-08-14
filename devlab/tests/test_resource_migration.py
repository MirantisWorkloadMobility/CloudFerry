import re
import pprint
import config
import unittest
import subprocess
import functional_test

from time import sleep
from generate_load import Prerequisites
from filtering_utils import FilteringUtils

NEUTRON_RESOURCES = ['networks', 'routers', 'subnets']
KEYSTONE_RESOURCES = ['tenants', 'users', 'roles']
NOVA_RESOURCES = ['servers', 'flavors', 'keypairs', 'security_groups']
GLANCE_RESOURCES = ['images']
CINDER_RESOURCES = ['volumes']


class ResourceMigrationTests(functional_test.FunctionalTest):

    def setUp(self):
        self.src_cloud = Prerequisites(cloud_prefix='SRC')
        self.dst_cloud = Prerequisites(cloud_prefix='DST')
        self.filtering_utils = FilteringUtils()

    def filter_resources(self, obj):
        def find_client(obj):
            if obj in KEYSTONE_RESOURCES:
                return self.src_cloud.keystoneclient
            elif obj in NOVA_RESOURCES:
                return self.src_cloud.novaclient
            elif obj in GLANCE_RESOURCES:
                return self.src_cloud.glanceclient
            elif obj in NEUTRON_RESOURCES:
                return self.src_cloud.neutronclient
            elif obj in CINDER_RESOURCES:
                return self.src_cloud.cinderclient

        cfg = self.filtering_utils.get_resources_from_config(obj)
        names = self.filtering_utils.get_resource_names(obj, cfg)
        if obj in NEUTRON_RESOURCES:
            net_list = getattr(find_client(obj), 'list_' + obj)()
            return {obj: [i for i in net_list[obj] if i['name'] in names]}
        opts = {}
        name_attr = 'name'
        if obj in CINDER_RESOURCES or obj in ['servers']:
            opts = {'search_opts': {'all_tenants': 1}}
            if obj in CINDER_RESOURCES:
                name_attr = 'display_name'

        client = getattr(find_client(obj), obj)
        return [i for i in client.list(**opts)
                if getattr(i, name_attr) in names]

    def validator(self, source_resources, dest_resources, resource_name):
        if not source_resources <= dest_resources:
            missing = source_resources - dest_resources
            self.fail("Not all {resources} migrated. Missing resources on dest: {missing}".format(
                resources=resource_name, missing=missing))

    def validate_resource_parameter_in_dst_dict(self, src_list, dst_list,
                                                resource_name='resource',
                                                parameter='name'):
        # Validating only uniq parameter's value
        source_resources = set([x[parameter] for x in src_list])
        dest_resources = set([x[parameter] for x in dst_list])
        self.validator(source_resources, dest_resources, resource_name)

    def validate_resource_parameter_in_dst(self, src_list, dst_list,
                                           resource_name='resource',
                                           parameter='name'):
        # Validating only uniq parameter's value
        source_resources = set([x.__dict__[parameter] for x in src_list])
        dest_resources = set([x.__dict__[parameter] for x in dst_list])
        self.validator(source_resources, dest_resources, resource_name)

    def validate_neutron_resource_parameter_in_dst(self, src_list, dst_list,
                                                   resource_name='networks',
                                                   parameter='name'):
        # Validating only uniq parameter's value
        source_resources = set([x[parameter] for x in src_list[resource_name]])
        dest_resources = set([x[parameter] for x in dst_list[resource_name]])
        self.validator(source_resources, dest_resources, resource_name)

    def test_migrate_keystone_users(self):
        src_users = self.filter_resources('users')
        dst_users = self.dst_cloud.keystoneclient.users.list()

        self.validate_resource_parameter_in_dst(src_users, dst_users,
                                                resource_name='user',
                                                parameter='name')
        self.validate_resource_parameter_in_dst(src_users, dst_users,
                                                resource_name='user',
                                                parameter='email')

    def test_migrate_keystone_roles(self):
        src_roles = self.filter_resources('roles')
        dst_roles = self.dst_cloud.keystoneclient.roles.list()

        self.validate_resource_parameter_in_dst(src_roles, dst_roles,
                                                resource_name='role',
                                                parameter='name')

    def test_migrate_keystone_tenants(self):
        src_tenants = self.filter_resources('tenants')
        dst_tenants = self.dst_cloud.keystoneclient.tenants.list()

        self.validate_resource_parameter_in_dst(src_tenants, dst_tenants,
                                                resource_name='tenant',
                                                parameter='name')
        self.validate_resource_parameter_in_dst(src_tenants, dst_tenants,
                                                resource_name='tenant',
                                                parameter='description')

    def test_migrate_nova_keypairs(self):
        src_keypairs = self.filter_resources('keypairs')
        dst_keypairs = self.dst_cloud.novaclient.keypairs.list()

        self.validate_resource_parameter_in_dst(src_keypairs, dst_keypairs,
                                                resource_name='keypair',
                                                parameter='name')
        self.validate_resource_parameter_in_dst(src_keypairs, dst_keypairs,
                                                resource_name='keypair',
                                                parameter='fingerprint')

    def test_migrate_nova_flavors(self):
        src_flavors = self.filter_resources('flavors')
        dst_flavors = self.dst_cloud.novaclient.flavors.list()

        self.validate_resource_parameter_in_dst(src_flavors, dst_flavors,
                                                resource_name='flavor',
                                                parameter='name')
        self.validate_resource_parameter_in_dst(src_flavors, dst_flavors,
                                                resource_name='flavor',
                                                parameter='ram')
        self.validate_resource_parameter_in_dst(src_flavors, dst_flavors,
                                                resource_name='flavor',
                                                parameter='vcpus')
        self.validate_resource_parameter_in_dst(src_flavors, dst_flavors,
                                                resource_name='flavor',
                                                parameter='disk')
        # Id can be changed, but for now in CloudFerry we moving flavor with
        # its id.
        self.validate_resource_parameter_in_dst(src_flavors, dst_flavors,
                                                resource_name='flavor',
                                                parameter='id')

    def test_migrate_nova_security_groups(self):
        src_sec_gr = self.filter_resources('security_groups')
        dst_sec_gr = self.dst_cloud.novaclient.security_groups.list()

        self.validate_resource_parameter_in_dst(src_sec_gr, dst_sec_gr,
                                                resource_name='security_group',
                                                parameter='name')
        self.validate_resource_parameter_in_dst(src_sec_gr, dst_sec_gr,
                                                resource_name='security_group',
                                                parameter='description')

    def test_migrate_glance_images(self):
        src_images = self.filter_resources('images')
        dst_images_gen = self.dst_cloud.glanceclient.images.list()
        dst_images = [x.__dict__ for x in dst_images_gen]

        filtering_data = self.filtering_utils.filter_images(src_images)
        src_images = filtering_data[0]

        self.validate_resource_parameter_in_dst_dict(src_images, dst_images,
                                                     resource_name='image',
                                                     parameter='name')
        self.validate_resource_parameter_in_dst_dict(src_images, dst_images,
                                                     resource_name='image',
                                                     parameter='disk_format')
        self.validate_resource_parameter_in_dst_dict(src_images, dst_images,
                                                     resource_name='image',
                                                     parameter='container_format')
        self.validate_resource_parameter_in_dst_dict(src_images, dst_images,
                                                     resource_name='image',
                                                     parameter='size')
        self.validate_resource_parameter_in_dst_dict(src_images, dst_images,
                                                     resource_name='image',
                                                     parameter='checksum')

    def test_glance_images_not_in_filter_did_not_migrate(self):
        src_images = self.filter_resources('images')
        filtering_data = self.filtering_utils.filter_images(src_images)
        dst_images_gen = self.dst_cloud.glanceclient.images.list()
        dst_images = [x.__dict__['name'] for x in dst_images_gen]
        images_filtered_out = filtering_data[1]
        for image in images_filtered_out:
            self.assertTrue(image['name'] not in dst_images, 'Image migrated despite '
                                                             'that it was not '
                                                             'included in filter, '
                                                             'Image info: \n{}'.format(image))

    def test_migrate_neutron_networks(self):
        src_nets = self.filter_resources('networks')
        dst_nets = self.dst_cloud.neutronclient.list_networks()

        self.validate_neutron_resource_parameter_in_dst(src_nets, dst_nets)
        self.validate_neutron_resource_parameter_in_dst(
            src_nets, dst_nets, parameter='provider:network_type')

    def test_migrate_neutron_subnets(self):
        src_subnets = self.filter_resources('subnets')
        dst_subnets = self.dst_cloud.neutronclient.list_subnets()

        self.validate_neutron_resource_parameter_in_dst(
            src_subnets, dst_subnets, resource_name='subnets')
        self.validate_neutron_resource_parameter_in_dst(
            src_subnets, dst_subnets, resource_name='subnets',
            parameter='gateway_ip')
        self.validate_neutron_resource_parameter_in_dst(
            src_subnets, dst_subnets, resource_name='subnets',
            parameter='cidr')

    def test_migrate_neutron_routers(self):
        src_routers = self.filter_resources('routers')
        dst_routers = self.dst_cloud.neutronclient.list_routers()

        self.validate_neutron_resource_parameter_in_dst(
            src_routers, dst_routers, resource_name='routers')

    def test_migrate_vms_parameters(self):
        src_vms_names = self.filter_resources('servers')
        dst_vms_names = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        src_vms = [x.__dict__ for x in src_vms_names]
        dst_vms = [x.__dict__ for x in dst_vms_names]

        filtering_data = self.filtering_utils.filter_vms(src_vms)
        src_vms = filtering_data[0]

        src_vms = [vm for vm in src_vms if vm['status'] != 'ERROR']

        self.validate_resource_parameter_in_dst_dict(
            src_vms, dst_vms, resource_name='VM', parameter='name')
        self.validate_resource_parameter_in_dst_dict(
            src_vms, dst_vms, resource_name='VM', parameter='config_drive')
        self.validate_resource_parameter_in_dst_dict(
            src_vms, dst_vms, resource_name='VM', parameter='key_name')

    def test_migrate_cinder_volumes(self):

        src_volume_list = self.filter_resources('volumes')
        dst_volume_list = self.dst_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})

        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='display_name')
        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='size')

    @unittest.skip("Temporarily disabled: snapshots doesn't implemented in "
                   "cinder's nfs driver")
    def test_migrate_cinder_snapshots(self):
        src_volume_list = self.filter_resources('volumes')
        dst_volume_list = self.dst_cloud.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})

        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='display_name')
        self.validate_resource_parameter_in_dst(
            src_volume_list, dst_volume_list, resource_name='volume',
            parameter='size')

    def test_migrate_tenant_quotas(self):
        """
        Validate tenant's quotas were migrated to correct tenant
        """
        def _delete_id_from_dict(_dict):
            for key in _dict:
                del _dict[key]['id']

        def check_and_delete_keys(tenant):
            return {key: dst_quotas[tenant][key] for key in dst_quotas[tenant]
                    if key in src_quotas[tenant]}

        src_quotas = {i.name: self.src_cloud.novaclient.quotas.get(i.id)._info
                      for i in self.filter_resources('tenants')}
        dst_quotas = {i.name: self.dst_cloud.novaclient.quotas.get(i.id)._info
                      for i in self.dst_cloud.keystoneclient.tenants.list()}

        # Delete tenant's ids
        _delete_id_from_dict(src_quotas)
        _delete_id_from_dict(dst_quotas)

        for tenant in src_quotas:
            self.assertIn(tenant, dst_quotas,
                          'Tenant %s is missing on dst' % tenant)
            # Delete quotas which we have on dst but do not have on src
            _dst_quotas = check_and_delete_keys(tenant)
            self.assertDictEqual(
                src_quotas[tenant], _dst_quotas,
                'Quotas for tenant %s on src and dst are different' % tenant)

    @unittest.skip("Temporarily disabled: test failed and should be fixed")
    def test_ssh_connectivity_by_keypair(self):
        def retry_cmd_execute(cmd):
            timeout = 300  # set timeout for retry 300 seconds
            for i in range(timeout):
                try:
                    subprocess.check_output(cmd, shell=True)
                    return
                except Exception:
                    sleep(1)
            raise RuntimeError("Command %s was failed" % cmd)

        dst_key_name = 'test_prv_key.pem'  # random name for new key

        ip_regexp = '.+(\d{3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).+'
        ip = re.match(ip_regexp, self.dst_cloud.auth_url).group(1)
        cmd = 'ssh -i {0} root@{1} "%s"'.format(config.dst_prv_key_path, ip)

        # create privet key on dst node
        create_key_cmd = "echo '{0}' > {1}".format(
            config.private_key['id_rsa'], dst_key_name)
        subprocess.check_output(cmd % create_key_cmd, shell=True)
        cmd_change_rights = 'chmod 400 %s' % dst_key_name
        subprocess.check_output(cmd % cmd_change_rights, shell=True)
        # find vm with valid keypair
        vms = self.dst_cloud.novaclient.servers.list(
            search_opts={'all_tenants': 1})
        for _vm in vms:
            if 'keypair_test' in _vm.name:
                vm = _vm
                break
        else:
            raise RuntimeError('VM for current test was not spawned')

        # get net id for ssh through namespace
        net_list = self.dst_cloud.neutronclient.list_networks()['networks']
        for net in net_list:
            if net['name'] in vm.networks:
                net_id = net['id']
                ip_address = vm.networks[net['name']].pop()
                break
        else:
            raise RuntimeError(
                "Networks for vm %s were not configured" % vm.name)

        cmd_ssh_to_vm = 'sudo ip netns exec {2} ssh' \
                        ' -o StrictHostKeyChecking=no -i {0} root@{1} date'
        cmd_ssh_to_vm = cmd_ssh_to_vm.format(dst_key_name, ip_address,
                                             'qdhcp-' + net_id)
        # make sure 22 port in sec group is open
        sec_grps = self.dst_cloud.get_sec_group_id_by_tenant_id(vm.tenant_id)
        for sec_gr in sec_grps:
            try:
                self.dst_cloud.create_security_group_rule(
                    sec_gr, vm.tenant_id, protocol='tcp', port_range_max=22,
                    port_range_min=22, direction='ingress')
            except Exception:
                pass

        try:
            retry_cmd_execute(cmd % cmd_ssh_to_vm)
        finally:
            subprocess.check_output(cmd % 'rm ' + dst_key_name, shell=True)

    def test_floating_ips_migrated(self):
        def get_fips(client):
            return set([fip['floating_ip_address']
                for fip in client.list_floatingips()['floatingips']])

        src_fips = get_fips(self.src_cloud.neutronclient)
        dst_fips = get_fips(self.dst_cloud.neutronclient)

        missing_fips = src_fips - dst_fips

        if missing_fips:
            self.fail("{num} floating IPs did not migrate to destination: "
                      "{fips}".format(num=len(missing_fips),
                      fips=pprint.pformat(missing_fips)))

