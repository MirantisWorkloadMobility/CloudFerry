# Copyright (c) 2016 Mirantis Inc.
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

import itertools
import unittest

from generator import generator, generate
from nose.plugins.attrib import attr

import cloudferry_devlab.tests.base as base
import cloudferry_devlab.tests.config as config
from cloudferry_devlab.tests import functional_test


@generator
class CinderMigrationTests(functional_test.FunctionalTest):
    """Test Case class which includes glance images migration cases."""

    def setUp(self):
        super(CinderMigrationTests, self).setUp()
        self.src_volume_list = self.filter_volumes()
        self.dst_volume_list = self.dst_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})

    @attr(migrated_tenant='tenant2')
    @generate('display_name', 'size', 'bootable', 'metadata',
              'volume_image_metadata')
    def test_migrate_cinder_volumes(self, param):
        """Validate volumes were migrated with correct parameters.

        :param name:
        :param size:
        :param bootable:
        :param metadata:"""

        def ignore_default_metadata(volumes):
            default_keys = ('readonly', 'attached_mode', 'src_volume_id')
            for vol in volumes:
                for default_key in default_keys:
                    if default_key in vol.metadata:
                        del vol.metadata[default_key]
            return volumes

        src_volume_list = ignore_default_metadata(self.src_volume_list)
        dst_volume_list = ignore_default_metadata(self.dst_volume_list)

        if param == 'volume_image_metadata':
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
            parameter=param)

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
            base.BasePrerequisites.wait_until_objects(
                [(vm_ip, 'pwd')],
                self.migration_utils.wait_until_vm_accessible_via_ssh,
                config.TIMEOUT)
            check_mount_point_exists(vm_ip, volume)
            cmd = 'mount {0} {1}'.format(volume['device'],
                                         volume['mount_point'])
            self.migration_utils.execute_command_on_vm(vm_ip, cmd,
                                                       warn_only=True)
            for _file in volume['write_to_file']:
                check_file_valid(volume['mount_point'] + _file['filename'])

    def test_cinder_volumes_not_in_filter_did_not_migrate(self):
        """Validate volumes not in filter weren't migrated."""
        dst_volumes = [x.id for x in self.dst_volume_list]

        filtering_data = self.filtering_utils.filter_volumes(
            self.src_volume_list)

        volumes_filtered_out = filtering_data[1]
        volumes_not_in_filter = []
        for volume in volumes_filtered_out:
            if volume.id in dst_volumes:
                volumes_not_in_filter.append(volume)
        if volumes_not_in_filter:
            self.fail(msg='Volumes migrated despite that it was not included '
                          'in filter, Volumes info: \n{}'.format(
                                volumes_not_in_filter))

    def test_invalid_status_cinder_volumes_did_not_migrate(self):
        """Validate volumes with invalid statuses weren't migrated.
        Statuses described in :mod:`config.py`
        """
        src_volume_list = self.src_cloud.cinderclient.volumes.list(
            search_opts={'all_tenants': 1})
        dst_volumes = [x.id for x in self.dst_volume_list]

        invalid_status_volumes = [
            vol for vol in src_volume_list
            if vol.status in config.INVALID_STATUSES
            ]

        invalid_volumes_migrated = []
        for volume in invalid_status_volumes:
            if volume.id in dst_volumes:
                invalid_volumes_migrated.append(volume)
        if invalid_volumes_migrated:
            self.fail(msg='Volume migrated despite that it had '
                          'invalid status, Volume info: \n{}'.format(
                                invalid_volumes_migrated))

    @generate('display_name', 'size')
    @unittest.skip("Temporarily disabled: snapshots doesn't implemented in "
                   "cinder's nfs driver")
    def test_migrate_cinder_snapshots(self, param):
        """Validate volume snapshots were migrated with correct parameters.

        :param name:
        :param size:"""
        dst_volume_list = self.dst_cloud.cinderclient.volume_snapshots.list(
            search_opts={'all_tenants': 1})

        self.validate_resource_parameter_in_dst(
            self.src_volume_list, dst_volume_list, resource_name='volume',
            parameter=param)
