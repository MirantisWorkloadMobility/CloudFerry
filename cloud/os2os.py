# Copyright (c) 2014 Mirantis Inc.
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


import cloud
import cloud_ferry
from cloudferrylib.base.action import copy_var, rename_info, merge, is_end_iter, get_info_iter
from cloudferrylib.os.actions import identity_transporter
from cloudferrylib.scheduler import scheduler
from cloudferrylib.scheduler import namespace
from cloudferrylib.scheduler import cursor
from cloudferrylib.os.image import glance_image
from cloudferrylib.os.storage import cinder_storage
from cloudferrylib.os.network import neutron
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.os.object_storage import swift_storage
from cloudferrylib.os.actions import get_info_images
from cloudferrylib.os.actions import transport_instance
from cloudferrylib.os.actions import attach_used_volumes_via_compute
from cloudferrylib.os.actions import cleanup_images
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import convert_image_to_compute
from cloudferrylib.os.actions import convert_image_to_volume
from cloudferrylib.os.actions import convert_compute_to_image
from cloudferrylib.os.actions import convert_compute_to_volume
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import convert_volume_to_compute
from cloudferrylib.os.actions import networks_transporter
from cloudferrylib.base.action import create_reference
from cloudferrylib.os.actions import prepare_volumes_data_map
from cloudferrylib.os.actions import get_info_instances
from cloudferrylib.os.actions import prepare_networks
from cloudferrylib.os.actions import instance_floatingip_actions
from cloudferrylib.os.actions import map_compute_info
from cloudferrylib.os.actions import deploy_volumes
from cloudferrylib.os.actions import check_instances
from cloudferrylib.os.actions import start_vm
from cloudferrylib.os.actions import load_compute_image_to_file
from cloudferrylib.os.actions import merge_base_and_diff
from cloudferrylib.os.actions import convert_file
from cloudferrylib.os.actions import upload_file_to_image
from cloudferrylib.os.actions import post_transport_instance
from cloudferrylib.os.actions import transport_ephemeral
from cloudferrylib.os.actions import is_not_transport_image
from cloudferrylib.os.actions import is_not_merge_diff
from cloudferrylib.os.actions import stop_vm
from cloudferrylib.utils import utils as utl
from cloudferrylib.os.actions import transport_compute_resources
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.os.actions import is_not_copy_diff_file
from cloudferrylib.utils.drivers import ssh_ceph_to_ceph
from cloudferrylib.utils.drivers import ssh_ceph_to_file
from cloudferrylib.utils.drivers import ssh_file_to_file
from cloudferrylib.utils.drivers import ssh_file_to_ceph
from cloudferrylib.utils.drivers import ssh_chunks
from cloudferrylib.os.actions import get_filter
from cloudferrylib.os.actions import deploy_snapshots
from cloudferrylib.base.action import is_option
from cloudferrylib.os.actions import get_info_volumes
from cloudferrylib.os.actions import get_info_objects
from cloudferrylib.os.actions import copy_object2object
from cloudferrylib.os.actions import fake_action
from cloudferrylib.os.actions import check_needed_compute_resources
from cloudferrylib.os.actions import check_ssh
from cloudferrylib.os.actions import check_sql
from cloudferrylib.os.actions import check_rabbitmq
from cloudferrylib.os.actions import check_bandwidth


class OS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(OS2OSFerry, self). __init__(config)
        resources = {'identity': keystone.KeystoneIdentity,
                     'image': glance_image.GlanceImage,
                     'storage': utl.import_class_by_string(
                         config.migrate.cinder_migration_strategy),
                     'network': neutron.NeutronNetwork,
                     'compute': nova_compute.NovaCompute,
                     'objstorage': swift_storage.SwiftStorage}
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources, cloud.DST, config)
        self.init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.config,
            'SSHCephToCeph': ssh_ceph_to_ceph.SSHCephToCeph,
            'SSHCephToFile': ssh_ceph_to_file.SSHCephToFile,
            'SSHFileToFile': ssh_file_to_file.SSHFileToFile,
            'SSHFileToCeph': ssh_file_to_ceph.SSHFileToCeph,
            'CopyFilesBetweenComputeHosts':
                ssh_chunks.CopyFilesBetweenComputeHosts,
        }

    def migrate(self, scenario=None):
        namespace_scheduler = namespace.Namespace({
            '__init_task__': self.init,
            'info_result': {
                utl.INSTANCES_TYPE: {}
            }
        })
        # "process_migration" is dict with 3 keys:
        #    "preparation" - is cursor that points to tasks must be processed
        #                    before migration i.e - taking snapshots,
        #                    figuring out all services are up
        #    "migration" - is cursor that points to the first
        #                  task in migration process
        #    "rollback" - is cursor that points to tasks must be processed
        #                 in case of "migration" failure
        if not scenario:
            process_migration = {"migration": cursor.Cursor(self.process_migrate())}
        else:
            scenario.init_tasks(self.init)
            scenario.load_scenario()
            process_migration = {k: cursor.Cursor(v) for k, v in scenario.get_net().items()}
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, **process_migration)
        scheduler_migr.start()

    def process_migrate(self):
        check_environment = self.check_environment()
        task_resources_transporting = self.transport_resources()
        transport_instances_and_dependency_resources = self.migrate_instances()
        return (check_environment >> 
                task_resources_transporting >> 
                transport_instances_and_dependency_resources)

    def check_environment(self):
        check_src_cloud = self.check_cloud('src_cloud')
        check_dst_cloud = self.check_cloud('dst_cloud')
        return check_src_cloud >> check_dst_cloud

    def check_cloud(self, cloud):
        read_instances = get_info_instances.GetInfoInstances(self.init,
                                                             cloud=cloud)
        read_images = get_info_images.GetInfoImages(self.init, cloud=cloud)
        read_objects = get_info_objects.GetInfoObjects(self.init, cloud=cloud)
        read_volumes = get_info_volumes.GetInfoVolumes(self.init, cloud=cloud)
        check_ssh_access = check_ssh.CheckSSH(self.init, cloud=cloud)
        sql_check = check_sql.CheckSQL(self.init, cloud=cloud)
        rabbit_check = check_rabbitmq.CheckRabbitMQ(self.init, cloud=cloud)
        bandwidh_check = check_bandwidth.CheckBandwidth(self.init, cloud=cloud)
        return (read_instances >>
                read_images >>
                read_objects >>
                read_volumes >>
                check_ssh_access >>
                sql_check >>
                rabbit_check >>
                bandwidh_check)

    def migrate_instances(self):
        name_data = 'info'
        name_result = 'info_result'
        name_backup = 'info_backup'
        name_iter = 'info_iter'
        save_result = self.save_result(name_data, name_result, name_result, 'instances')
        trans_one_inst = self.migrate_process_instance()
        init_iteration_instance = self.init_iteration_instance(name_data, name_backup, name_iter)
        act_check_needed_compute_resources = check_needed_compute_resources.CheckNeededComputeResources(self.init)
        act_get_filter = get_filter.GetFilter(self.init)
        act_get_info_inst = get_info_instances.GetInfoInstances(self.init, cloud='src_cloud')
        act_cleanup_images = cleanup_images.CleanupImages(self.init)
        get_next_instance = get_info_iter.GetInfoIter(self.init)
        check_for_instance = check_instances.CheckInstances(self.init)
        rename_info_iter = rename_info.RenameInfo(self.init, name_result, name_data)
        is_instances = is_end_iter.IsEndIter(self.init)

        transport_instances_and_dependency_resources = \
            act_get_filter >> \
            act_get_info_inst >> \
            init_iteration_instance >> \
            act_check_needed_compute_resources >> \
            (check_for_instance | rename_info_iter) >> \
            get_next_instance >> \
            trans_one_inst >> \
            save_result >> \
            (is_instances | get_next_instance) >>\
            rename_info_iter >> \
            act_cleanup_images
        return transport_instances_and_dependency_resources

    def init_iteration_instance(self, data, name_backup, name_iter):
        init_iteration_instance = copy_var.CopyVar(self.init, data, name_backup, True) >>\
                                  create_reference.CreateReference(self.init, data, name_iter)
        return init_iteration_instance

    def migration_images(self):
        act_get_info_images = get_info_images.GetInfoImages(self.init, cloud='src_cloud')
        act_deploy_images = copy_g2g.CopyFromGlanceToGlance(self.init)
        return act_get_info_images >> act_deploy_images

    def save_result(self, data1, data2, result, resources_name):
        return merge.Merge(self.init, data1, data2, result, resources_name)

    def transport_volumes_by_instance(self):
        act_copy_g2g_vols = copy_g2g.CopyFromGlanceToGlance(self.init)
        act_convert_c_to_v = convert_compute_to_volume.ConvertComputeToVolume(self.init, cloud='src_cloud')
        act_convert_v_to_i = convert_volume_to_image.ConvertVolumeToImage(self.init, cloud='src_cloud')
        act_convert_i_to_v = convert_image_to_volume.ConvertImageToVolume(self.init, cloud='dst_cloud')
        act_convert_v_to_c = convert_volume_to_compute.ConvertVolumeToCompute(self.init, cloud='dst_cloud')
        task_convert_c_to_v_to_i = act_convert_c_to_v >> act_convert_v_to_i
        task_convert_i_to_v_to_c = act_convert_i_to_v >> act_convert_v_to_c
        return task_convert_c_to_v_to_i >> act_copy_g2g_vols >> task_convert_i_to_v_to_c

    def transport_volumes_by_instance_via_ssh(self):
        act_convert_c_to_v = convert_compute_to_volume.ConvertComputeToVolume(self.init, cloud='src_cloud')
        act_rename_inst_vol_src = create_reference.CreateReference(self.init, 'storage_info',
                                                                   'src_storage_info')
        act_convert_v_to_c = convert_volume_to_compute.ConvertVolumeToCompute(self.init, cloud='dst_cloud')
        act_rename_inst_vol_dst = create_reference.CreateReference(self.init, 'storage_info',
                                                                   'dst_storage_info')
        act_inst_vol_data_map = prepare_volumes_data_map.PrepareVolumesDataMap(self.init,
                                                                               'src_storage_info',
                                                                               'dst_storage_info')
        act_deploy_inst_volumes = deploy_volumes.DeployVolumes(self.init, cloud='dst_cloud')

        act_inst_vol_transport_data = task_transfer.TaskTransfer(self.init,
                                                                 'SSHCephToCeph',
                                                                 input_info='storage_info')

        act_deploy_snapshots = deploy_snapshots.DeployVolSnapshots(self.init, cloud='dst_cloud') - act_convert_v_to_c

        is_snapshots = is_option.IsOption(self.init, 'keep_volume_snapshots')

        task_get_inst_vol_info = act_convert_c_to_v >> act_rename_inst_vol_src
        task_deploy_inst_vol = act_deploy_inst_volumes >> act_rename_inst_vol_dst
        return task_get_inst_vol_info >> \
               task_deploy_inst_vol >> act_inst_vol_data_map >> \
               (is_snapshots | act_deploy_snapshots | act_inst_vol_transport_data) >> \
               act_convert_v_to_c

    def transport_available_volumes_via_ssh(self):
        is_volume_snapshots = is_option.IsOption(self.init,
                                                 'keep_volume_snapshots')

        final_action = fake_action.FakeAction(self.init)

        act_get_info_available_volumes = get_info_volumes.GetInfoVolumes(self.init,
                                                                         cloud='src_cloud',
                                                                         search_opts={'status': 'available'})
        act_rename_vol_src = create_reference.CreateReference(self.init,
                                                              'storage_info',
                                                              'src_storage_info')
        task_get_available_vol_info = act_get_info_available_volumes >> act_rename_vol_src

        act_deploy_vol = deploy_volumes.DeployVolumes(self.init,
                                                      cloud='dst_cloud')
        act_rename_vol_dst = create_reference.CreateReference(self.init,
                                                              'storage_info',
                                                              'dst_storage_info')
        task_deploy_available_volumes = act_deploy_vol >> act_rename_vol_dst

        act_vol_data_map = prepare_volumes_data_map.PrepareVolumesDataMap(self.init,
                                                                          'src_storage_info',
                                                                          'dst_storage_info')

        act_vol_transport_data = \
            task_transfer.TaskTransfer(self.init,
                                       'SSHCephToCeph',
                                       input_info='storage_info') - final_action

        act_deploy_vol_snapshots = \
            deploy_snapshots.DeployVolSnapshots(self.init,cloud='dst_cloud') - final_action

        return task_get_available_vol_info >> \
               task_deploy_available_volumes >> \
               act_vol_data_map >> \
               (is_volume_snapshots | act_deploy_vol_snapshots | act_vol_transport_data) \
               >> final_action

    def transport_object_storage(self):
        act_get_objects_info = get_info_objects.GetInfoObjects(self.init,
                                                               cloud='src_cloud')
        act_transfer_objects = copy_object2object.CopyFromObjectToObject(self.init,
                                                                         src_cloud='src_cloud',
                                                                         dst_cloud='dst_cloud')
        task_transfer_objects = act_get_objects_info >> act_transfer_objects
        return task_transfer_objects

    def transport_cold_data(self):
        act_identity_trans = identity_transporter.IdentityTransporter(self.init)
        task_transport_available_volumes = self.transport_available_volumes_via_ssh()
        task_transport_objects = self.transport_object_storage()
        task_transport_images = self.migration_images()
        return act_identity_trans >> \
               task_transport_available_volumes \
               >> task_transport_objects \
               >> task_transport_images

    def transport_resources(self):
        act_identity_trans = identity_transporter.IdentityTransporter(self.init)
        task_images_trans = self.migration_images()
        act_comp_res_trans = transport_compute_resources.TransportComputeResources(self.init)
        act_network_trans = networks_transporter.NetworkTransporter(self.init)
        return act_identity_trans >> task_images_trans >> act_network_trans >> act_comp_res_trans

    def migrate_images_by_instances(self):
        act_conv_comp_img = convert_compute_to_image.ConvertComputeToImage(self.init, cloud='src_cloud')
        act_conv_image_comp = convert_image_to_compute.ConvertImageToCompute(self.init)
        act_copy_inst_images = copy_g2g.CopyFromGlanceToGlance(self.init)
        return act_conv_comp_img >> act_copy_inst_images >> act_conv_image_comp

    def migrate_resources_by_instance(self):
        transport_images = self.migrate_images_by_instances()
        task_transport_volumes = self.transport_volumes_by_instance()
        return transport_images >> task_transport_volumes

    def migrate_resources_by_instance_via_ssh(self):
        transport_images = self.migrate_images_by_instances()
        task_transport_volumes = self.transport_volumes_by_instance_via_ssh()
        return transport_images >> task_transport_volumes

    def migrate_instance(self):
        act_map_com_info = map_compute_info.MapComputeInfo(self.init)
        act_net_prep = prepare_networks.PrepareNetworks(self.init, cloud='dst_cloud')
        act_deploy_instances = transport_instance.TransportInstance(self.init)
        act_i_to_f = load_compute_image_to_file.LoadComputeImageToFile(self.init, cloud='dst_cloud')
        act_merge = merge_base_and_diff.MergeBaseDiff(self.init, cloud='dst_cloud')
        act_convert_image = convert_file.ConvertFile(self.init, cloud='dst_cloud')
        act_f_to_i = upload_file_to_image.UploadFileToImage(self.init, cloud='dst_cloud')
        act_transfer_file = task_transfer.TaskTransfer(self.init, 'SSHCephToFile',
                                                       resource_name=utl.INSTANCES_TYPE,
                                                       resource_root_name=utl.DIFF_BODY)
        act_f_to_i_after_transfer = upload_file_to_image.UploadFileToImage(self.init, cloud='dst_cloud')
        act_is_not_trans_image = is_not_transport_image.IsNotTransportImage(self.init, cloud='src_cloud')
        act_is_not_merge_diff = is_not_merge_diff.IsNotMergeDiff(self.init, cloud='src_cloud')
        act_post_transport_instance = post_transport_instance.PostTransportInstance(self.init, cloud='dst_cloud')
        act_transport_ephemeral = transport_ephemeral.TransportEphemeral(self.init, cloud='dst_cloud')
        trans_file_to_file = task_transfer.TaskTransfer(
            self.init,
            'SSHFileToFile',
            resource_name=utl.INSTANCES_TYPE,
            resource_root_name=utl.DIFF_BODY)
        act_trans_diff_file = task_transfer.TaskTransfer(
            self.init,
            'SSHFileToFile',
            resource_name=utl.INSTANCES_TYPE,
            resource_root_name=utl.DIFF_BODY)
        act_is_not_copy_diff_file = is_not_copy_diff_file.IsNotCopyDiffFile(self.init)
        process_merge_diff_and_base = act_i_to_f >> trans_file_to_file >> act_merge >> act_convert_image >> act_f_to_i
        process_merge_diff_and_base = act_i_to_f
        process_transport_image = act_transfer_file >> act_f_to_i_after_transfer
        process_transport_image = act_transfer_file
        act_pre_transport_instance = (act_is_not_trans_image | act_is_not_merge_diff) >> \
                                     process_transport_image >> \
                                     (act_is_not_merge_diff | act_deploy_instances) >> \
                                     process_merge_diff_and_base
        act_post_transport_instance = (act_is_not_copy_diff_file |
                                       act_transport_ephemeral) >> act_trans_diff_file
        return act_net_prep >> \
               act_map_com_info >> \
               act_pre_transport_instance >> \
               act_deploy_instances >> \
               act_post_transport_instance >> \
               act_transport_ephemeral

    def migrate_process_instance(self):
        act_attaching = attach_used_volumes_via_compute.AttachVolumesCompute(self.init, cloud='dst_cloud')
        act_stop_vms = stop_vm.StopVms(self.init, cloud='src_cloud')
        act_start_vms = start_vm.StartVms(self.init, cloud='dst_cloud')
        #transport_resource_inst = self.migrate_resources_by_instance_via_ssh()
        transport_resource_inst = self.migrate_resources_by_instance()
        transport_inst = self.migrate_instance()
        act_dissociate_floatingip = instance_floatingip_actions.DisassociateAllFloatingips(self.init, cloud='src_cloud')
        return act_stop_vms >> transport_resource_inst >> transport_inst >> \
               act_attaching >> act_dissociate_floatingip >> act_start_vms
