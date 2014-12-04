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
from cloudferrylib.base.action import copy_var, rename_info, merge, is_end_iter, get_info_iter, create_reference
from cloudferrylib.os.actions import identity_transporter
from cloudferrylib.scheduler import scheduler
from cloudferrylib.scheduler import namespace
from cloudferrylib.scheduler import cursor
from cloudferrylib.os.image import glance_image
from cloudferrylib.os.storage import cinder_storage
from cloudferrylib.os.network import neutron
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.object_storage import swift_storage
from cloudferrylib.os.compute import nova_compute
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
from cloudferrylib.os.actions import attach_used_volumes
from cloudferrylib.os.actions import networks_transporter
from cloudferrylib.base.action import create_reference
from cloudferrylib.os.actions import prepare_volumes_data_map
from cloudferrylib.os.actions import transport_ceph_to_ceph_via_ssh
from cloudferrylib.os.actions import get_info_instances
from cloudferrylib.os.actions import prepare_networks
from cloudferrylib.os.actions import map_compute_info
from cloudferrylib.os.actions import start_vm
from cloudferrylib.os.actions import stop_vm
from cloudferrylib.utils import utils as utl
from cloudferrylib.os.actions import transport_compute_resources
from cloudferrylib.os.actions import merge


class OS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(OS2OSFerry, self). __init__(config)
        resources = {'identity': keystone.KeystoneIdentity,
                     'image': glance_image.GlanceImage,
                     'storage': cinder_storage.CinderStorage,
                     'network': neutron.NeutronNetwork,
                     'compute': nova_compute.NovaCompute,
                     'objstorage': swift_storage.SwiftStorage}
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources, cloud.DST, config)
        self.init = {
            'src_cloud': self.src_cloud,
            'dst_cloud': self.dst_cloud,
            'cfg': self.config
        }

    def migrate(self):
        namespace_scheduler = namespace.Namespace({
            '__init_task__': self.init,
            'info_result': {
                utl.COMPUTE_RESOURCE: {utl.INSTANCES_TYPE: {}}
            }
        })

        task_resources_transporting = self.transport_resources()
        transport_instances_and_dependency_resources = self.migrate_instances()

        process_migration = task_resources_transporting >> transport_instances_and_dependency_resources

        process_migration = cursor.Cursor(process_migration)
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, cursor=process_migration)
        scheduler_migr.start()

    def migrate_instances(self):
        name_data = 'info'
        name_result = 'info_result'
        name_backup = 'info_backup'
        name_iter = 'info_iter'
        save_result = self.save_result(name_data, name_result, name_result, 'compute', 'instances')
        trans_one_inst = self.migrate_process_instance()
        init_iteration_instance = self.init_iteration_instance(name_data, name_backup, name_iter)
        act_get_info_inst = get_info_instances.GetInfoInstances(self.init, cloud='src_cloud')
        act_cleanup_images = cleanup_images.CleanupImages(self.init)
        get_next_instance = get_info_iter.GetInfoIter()
        rename_info_iter = rename_info.RenameInfo(name_result, name_data)
        is_instances = is_end_iter.IsEndIter()

        transport_instances_and_dependency_resources = \
            act_get_info_inst >> \
            init_iteration_instance >> \
            get_next_instance >> \
            trans_one_inst >> \
            save_result >> \
            (is_instances | get_next_instance) >>\
            rename_info_iter >> \
            act_cleanup_images
        return transport_instances_and_dependency_resources

    def init_iteration_instance(self, data, name_backup, name_iter):
        init_iteration_instance = copy_var.CopyVar(data, name_backup, True) >>\
                                  create_reference.CreateReference(data, name_iter)
        return init_iteration_instance

    def migration_images(self):
        act_get_info_images = get_info_images.GetInfoImages(self.init, cloud='src_cloud')
        act_deploy_images = copy_g2g.CopyFromGlanceToGlance(self.init)
        return act_get_info_images >> act_deploy_images

    def save_result(self, data1, data2, result, resource_type, resources_name):
        return merge.Merge(data1, data2, result, resource_type, resources_name)

    def transport_volumes_by_instance(self):
        act_copy_g2g_vols = copy_g2g.CopyFromGlanceToGlance(self.init)
        act_convert_c_to_v = convert_compute_to_volume.ConvertComputeToVolume(self.init, cloud='src_cloud')
        act_convert_v_to_i = convert_volume_to_image.ConvertVolumeToImage(self.init, cloud='src_cloud')
        act_convert_i_to_v = convert_image_to_volume.ConvertImageToVolume(self.init, cloud='dst_cloud')
        act_convert_v_to_c = convert_volume_to_compute.ConvertVolumeToCompute(self.init, cloud='dst_cloud')
        task_convert_c_to_v_to_i = act_convert_c_to_v >> act_convert_v_to_i
        task_convert_i_to_v_to_c = act_convert_i_to_v >> act_convert_v_to_c
        return task_convert_c_to_v_to_i >> act_copy_g2g_vols >> task_convert_i_to_v_to_c

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

    def migrate_instance(self):
        act_map_com_info = map_compute_info.MapComputeInfo(self.init)
        act_net_prep = prepare_networks.PrepareNetworks(self.init, cloud='dst_cloud')
        act_deploy_instances = transport_instance.TransportInstance(self.init)
        return act_net_prep >> act_map_com_info >> act_deploy_instances

    def migrate_process_instance(self):
        act_attaching = attach_used_volumes_via_compute.AttachVolumesCompute(self.init, cloud='dst_cloud')
        act_stop_vms = stop_vm.StopVms(self.init, cloud='src_cloud')
        act_start_vms = start_vm.StartVms(self.init, cloud='dst_cloud')
        transport_resource_inst = self.migrate_resources_by_instance()
        transport_inst = self.migrate_instance()
        return act_stop_vms >> transport_resource_inst >> transport_inst >> act_attaching >> act_start_vms
