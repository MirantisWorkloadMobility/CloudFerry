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
"""
# Overview

Implements intercloud live migration functionality.

# Live migration process

 1. Create fake VM on destination node using nova APIs with the same dependent
    objects (networks, images, flavors, etc).
    - This creates all the infrastructure needed for VM to work properly (such
      as virtual network interfaces, openvswitch ports, iptables rules, etc).
 2. Stop nova-compute on destination host
    - This allows us to work with VM at the libvirt level, without Nova
      "knowing" about it
 3. Merge source VM libvirt XML with destination fake VM libvirt XML
    - Source libvirt XML contains source-specific values (virtual network
      interface names, network namespace names, etc), which are invalid on
      destination. Those must be updated with destination node values.
 4. Destroy VM on destination from libvirt level
 5. Live migrate VM using libvirt using XML from step above
 6. Start nova compute on destination

# Tested on

 - Grizzly to Icehouse
"""


import os
from fabric.operations import prompt

import cfglib
from cloudferrylib.base.action import action
from cloudferrylib.os.compute import libvirt
from cloudferrylib.os.compute.nova_compute import instance_host
from cloudferrylib.os.compute.nova_compute import instance_libvirt_name
from cloudferrylib.utils import files
from cloudferrylib.utils import log
from cloudferrylib.utils import ubuntu
from cloudferrylib.utils import remote_runner
from cloudferrylib.utils import utils


LOG = log.getLogger(__name__)


class LiveMigration(action.Action):
    """
    Runs live migration of VMs

    Process:
     - Create fake VM on DST using nova
     - Update SRC VM's libvirt XML with DST devices
     - Disable nova-compute on DST so that we can replace VM image with
       libvirt. Otherwise nova will track instance state, which we don't want.
     - Destroy fake VM on DST from the libvirt level, so that all the
       infrastructure (virtual networking) required for VM is left intact
     - Live-migrate instance
     - Enable nova-compute on DST

    Requires:
     - qemu 2.0 on source and destination compute nodes
     - remote privileged SSH access to compute nodes
    """

    def run(self, info=None, **kwargs):
        new_id, instance = info[utils.INSTANCES_TYPE].items()[0]
        old_id = instance['old_id']

        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]
        src_compute = self.src_cloud.resources[utils.COMPUTE_RESOURCE]

        dst_compute.change_status('active', instance_id=new_id)

        dst_instance = dst_compute.get_instance(new_id)
        src_instance = src_compute.get_instance(old_id)

        # do not attempt to live migrate inactive instances
        if src_instance.status.lower() not in ['active', 'verify_resize']:
            LOG.debug("Skipping live migration of VM '%s', because it's "
                      "inactive", src_instance.name)
            return

        src_host = instance_host(src_instance)
        dst_host = instance_host(dst_instance)

        src_runner = remote_runner.RemoteRunner(src_host,
                                                cfglib.CONF.src.ssh_user)
        dst_runner = remote_runner.RemoteRunner(dst_host,
                                                cfglib.CONF.dst.ssh_user)

        src_libvirt = libvirt.Libvirt(src_runner)
        dst_libvirt = libvirt.Libvirt(dst_runner)

        src_virsh_name = instance_libvirt_name(src_instance)
        dst_virsh_name = instance_libvirt_name(dst_instance)

        src_vm_xml = src_libvirt.get_xml(src_virsh_name)
        dst_vm_xml = dst_libvirt.get_xml(dst_virsh_name)

        src_vm_xml.disk_file = dst_vm_xml.disk_file
        src_vm_xml.serial_file = dst_vm_xml.serial_file
        src_vm_xml.console_file = dst_vm_xml.console_file
        src_vm_xml.interfaces = dst_vm_xml.interfaces

        dst_backing_file = dst_libvirt.get_backing_file(new_id)
        src_backing_file = src_libvirt.get_backing_file(old_id)
        migration_backing_file = os.path.join(
            libvirt.nova_instances_path,
            '_base',
            'migration_disk_{}'.format(old_id))
        dst_compute.wait_for_status(new_id, dst_compute.get_status, 'active')

        with files.RemoteTempFile(src_runner,
                                  "migrate-{}".format(old_id),
                                  src_vm_xml.dump()) as migration_file,\
                files.RemoteSymlink(src_runner,
                                    src_backing_file,
                                    migration_backing_file),\
                files.RemoteSymlink(dst_runner,
                                    dst_backing_file,
                                    migration_backing_file),\
                ubuntu.StopNovaCompute(dst_runner),\
                libvirt.QemuBackingFileMover(src_libvirt.runner,
                                             migration_backing_file,
                                             old_id):

            destroyer = libvirt.DestNovaInstanceDestroyer(dst_libvirt,
                                                          dst_compute,
                                                          dst_virsh_name,
                                                          dst_instance.id)
            try:
                destroyer.do()
                src_libvirt.live_migrate(src_virsh_name,
                                         dst_host,
                                         migration_file.filename)
            except remote_runner.RemoteExecutionError:
                destroyer.undo()
            finally:
                dst_libvirt.move_backing_file(dst_backing_file, new_id)


class UpdateInstancesAutoIncrement(action.Action):
    """Updates `nova.instances` auto increment value on destination. This is
    required to match libvirt instance IDs on source and destination. Libvirt
    instance IDs must be identical on source and destination for live migration

    Requirements:
      - Write access to nova DB on destination
    """
    def run(self, info=None, **kwargs):
        instance_id = info[utils.INSTANCES_TYPE].keys()[0]
        mysql_id = self.src_cloud.resources[utils.COMPUTE_RESOURCE].\
            get_instance_sql_id_by_uuid(instance_id)
        self.dst_cloud.resources[
            utils.COMPUTE_RESOURCE].update_instance_auto_increment(mysql_id)


class RestoreOriginalInstancesTableSchema(action.Action):
    """Restores original value of `nova.instances` auto-increment. Should be
    used together with `UpdateInstancesAutoIncrement`

    Requirements:
      - Write access to nova DB on destination
    """
    def run(self, info=None, **kwargs):
        nova_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]
        mysql = nova_compute.mysql_connector
        reset_instances_id = ("alter table instances change id id INT (11) "
                              "not null auto_increment")
        LOG.info("Resetting nova.instances.id column to original value")
        mysql.execute(reset_instances_id)


class CheckQemuVersion(action.Action):
    """Verifies qemu version is 2.0 on all source and destination compute
    nodes. This is the primary requirement for live migration.

    Requirements:
     - ssh access to compute nodes
    """

    REQUIRED_QEMU_VERSION = "2.0"

    def run(self, info=None, **kwargs):
        faulty_hosts = []

        for cloud in [self.src_cloud, self.dst_cloud]:
            nova_compute = cloud.resources[utils.COMPUTE_RESOURCE]
            hosts = nova_compute.get_compute_hosts()

            for host in hosts:
                runner = remote_runner.RemoteRunner(
                    host, cloud.cloud_config.cloud.ssh_user)

                qemu_version_cmd = ("kvm -version | "
                                    "sed -E 's/QEMU emulator version "
                                    "([0-9]\\.[0-9]\\.?[0-9]?).*/\\1/'")

                version = runner.run(qemu_version_cmd)

                if self.REQUIRED_QEMU_VERSION not in version:
                    faulty_hosts.append(host)

        if faulty_hosts:
            msg = ("qemu must be upgraded to v{required} on following hosts: "
                   "{hosts}").format(required=self.REQUIRED_QEMU_VERSION,
                                     hosts=faulty_hosts)
            LOG.error(msg)
            raise RuntimeError(msg)


class CheckNovaInstancesTable(action.Action):
    """Verifies if CloudFerry can proceed with live migration based on the
    contents of `nova.instances` table.

    Live migration may fail if `nova.instances` table on source has ids
    (`nova.instance.id`) which are also present on destination.

    Requires:
     - Nova DB connectivity on source
     - Nova DB connectivity on destination
    """

    def run(self, **kwargs):
        src_compute = self.src_cloud.resources[utils.COMPUTE_RESOURCE]
        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]

        src_mysql = src_compute.mysql_connector
        dst_mysql = dst_compute.mysql_connector

        def get_instance_ids(mysql):
            get_ids = "select id from nova.instances where deleted = 0"
            return set([row.values()[0]
                        for row in mysql.execute(get_ids).fetchall()])

        src_ids = get_instance_ids(src_mysql)
        dst_ids = get_instance_ids(dst_mysql)

        LOG.debug("SRC IDs: %s", src_ids)
        LOG.debug("DST IDs: %s", dst_ids)

        has_identical_ids = len(src_ids & dst_ids) > 0

        if has_identical_ids:
            message = (
                "Cannot proceed with live migration because destination cloud "
                "has `nova.instance.ids` equal to those on source cloud. "
                "Migration will be aborted.")

            LOG.error(message)
            raise RuntimeError(message)
        else:
            LOG.info("There are no identical nova instance IDs on source and "
                     "dest, can proceed with live migration")


class CleanupDestinationInstancesDB(action.Action):
    """Cleans up `nova.instances` MySQL table with all it's constraints from
    destination cloud.

    Requirements:
     - Write MySQL access on destination

    Tested on:
     - Openstack Icehouse release

    Limitations:
     - Does not work with Juno. Use `CleanupDestinationInstancesDBJuno` instead
    """

    tables_to_remove = [
        'block_device_mapping',
        'instance_actions_events',
        'instance_actions',
        'instance_faults',
        'instance_info_caches',
        'instance_system_metadata',
        'instances'
    ]

    def run(self, **kwargs):
        dst_compute = self.dst_cloud.resources[utils.COMPUTE_RESOURCE]
        dst_mysql = dst_compute.mysql_connector

        def affirmative(ans):
            return ans in ['Y', 'y', 'yes']

        answer = prompt("This will REMOVE ALL DATA from nova instances on "
                        "destination cloud! Are you sure? (Y/N)")

        proceed_with_removal = False

        if affirmative(answer):
            answer = prompt("No, seriously, THIS WILL REMOVE ABSOLUTELY "
                            "EVERYTHING from nova.instances DB table on "
                            "destination cloud. ARE YOU SURE? (Y/N)")
            if affirmative(answer):
                proceed_with_removal = True

        if proceed_with_removal:
            LOG.warning("Following tables will be removed on destination: %s",
                        self.tables_to_remove)
            for table in self.tables_to_remove:
                delete_sql = "delete from nova.{table}".format(table=table)
                dst_mysql.execute(delete_sql)


class CleanupDestinationInstancesDBJuno(CleanupDestinationInstancesDB):
    """Cleans up `nova.instances` MySQL table from destination cloud when
    destination is Juno release of Openstack.

    Requirements:
     - Write MySQL access on destination

    Tested on
     - Openstack Juno release
    """

    tables_to_remove = [
        'block_device_mapping',
        'instance_extra',
        'instance_actions_events',
        'instance_actions',
        'instance_faults',
        'instance_info_caches',
        'instance_system_metadata',
        'instances'
    ]
