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
from cloudferrylib.os.actions import identity_transporter
from cloudferrylib.scheduler import scheduler
from cloudferrylib.scheduler import namespace
from cloudferrylib.scheduler import cursor
from cloudferrylib.os.image import glance_image
from cloudferrylib.os.storage import cinder_storage
from cloudferrylib.os.network import neutron
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.os.actions import get_info_volumes
from cloudferrylib.os.actions import get_info_images
from cloudferrylib.os.actions import deploy_volumes
from cloudferrylib.os.actions import transport_instance
from cloudferrylib.os.actions import attach_used_volumes_via_compute
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import convert_image_to_compute
from cloudferrylib.os.actions import convert_image_to_volume
from cloudferrylib.os.actions import convert_compute_to_image
from cloudferrylib.os.actions import convert_compute_to_volume
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import convert_volume_to_compute
from cloudferrylib.os.actions import attach_used_volumes
from cloudferrylib.os.actions import create_reference
from cloudferrylib.os.actions import prepare_volumes_data_map
from cloudferrylib.os.actions import transport_ceph_to_ceph_via_ssh
from cloudferrylib.os.actions import get_info_instances
from cloudferrylib.os.actions import prepare_networks
from cloudferrylib.os.actions import map_compute_info
from cloudferrylib.os.actions import get_info_iter
from cloudferrylib.os.actions import start_vm
from cloudferrylib.os.actions import stop_vm
from cloudferrylib.os.actions import copy_var
from cloudferrylib.os.actions import networks_transporter
from cloudferrylib.scheduler import task
from cloudferrylib.utils import utils as utl
from cloudferrylib.os.actions import transport_compute_resources


class OS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(OS2OSFerry, self). __init__(config)
        resources = {'identity': keystone.KeystoneIdentity,
                     'image': glance_image.GlanceImage,
                     'storage': cinder_storage.CinderStorage,
                     'network': neutron.NeutronNetwork,
                     'compute': nova_compute.NovaCompute}
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources, cloud.DST, config)
        
    def migrate(self):

        act_identity_trans = identity_transporter.IdentityTransporter(self.src_cloud, self.dst_cloud)
        act_comp_res_trans = transport_compute_resources.TransportComputeResources(self.src_cloud, self.dst_cloud)

        act_get_info_images = get_info_images.GetInfoImages(self.src_cloud)
        act_get_info_inst = get_info_instances.GetInfoInstances(self.src_cloud)

        act_conv_comp_img = convert_compute_to_image.ConvertComputeToImage(self.config, self.src_cloud)
        act_conv_image_comp = convert_image_to_compute.ConvertImageToCompute()
        act_map_com_info = map_compute_info.MapComputeInfo(self.src_cloud, self.dst_cloud)
        act_stop_vms = stop_vm.StopVms(self.src_cloud)

        act_deploy_images = copy_g2g.CopyFromGlanceToGlance(self.src_cloud, self.dst_cloud)
        act_copy_inst_images = copy_g2g.CopyFromGlanceToGlance(self.src_cloud, self.dst_cloud)
        act_net_prep = prepare_networks.PrepareNetworks(self.dst_cloud, self.config)
        act_deploy_instances = transport_instance.TransportInstance(self.config, self.src_cloud, self.dst_cloud)


        act_copy_g2g_vols = copy_g2g.CopyFromGlanceToGlance(self.src_cloud, self.dst_cloud)
        act_convert_c_to_v = convert_compute_to_volume.ConvertComputeToVolume(self.config, self.src_cloud)
        act_convert_v_to_i = convert_volume_to_image.ConvertVolumeToImage('qcow2', self.src_cloud)
        act_convert_i_to_v = convert_image_to_volume.ConvertImageToVolume(self.dst_cloud)
        act_convert_v_to_c = convert_volume_to_compute.ConvertVolumeToCompute(self.dst_cloud)
        act_convert_c_to_v_attach = convert_compute_to_volume.ConvertComputeToVolume(self.config, self.src_cloud)
        act_attaching = attach_used_volumes_via_compute.AttachVolumesCompute(self.dst_cloud)

        act_deploy_inst_volumes = deploy_volumes.DeployVolumes(self.dst_cloud)
        act_rename_inst_vol_src = create_reference.CreateReference('storage_info',
                                                              'src_storage_info')
        act_rename_inst_vol_dst = create_reference.CreateReference('storage_info',
                                                              'dst_storage_info')
        act_inst_vol_data_map = prepare_volumes_data_map.PrepareVolumesDataMap('src_storage_info',
                                                                          'dst_storage_info')
        act_inst_vol_transport_data = transport_ceph_to_ceph_via_ssh.TransportCephToCephViaSsh(self.config,
                                                                                      self.src_cloud,
                                                                                      self.dst_cloud,
                                                                                      input_info='storage_info')

        act_get__available_vol_info = \
            get_info_volumes.GetInfoVolumes(self.src_cloud, search_opts={'status': 'available'})

        act_deploy_available_volumes = deploy_volumes.DeployVolumes(self.dst_cloud)
        act_rename_available_vol_src = create_reference.CreateReference('storage_info',
                                                              'src_storage_info')
        act_rename_available_vol_dst = create_reference.CreateReference('storage_info',
                                                              'dst_storage_info')
        act_available_vol_data_map = prepare_volumes_data_map.PrepareVolumesDataMap('src_storage_info',
                                                                          'dst_storage_info')
        act_available_vol_transport_data = transport_ceph_to_ceph_via_ssh.TransportCephToCephViaSsh(self.config,
                                                                                      self.src_cloud,
                                                                                      self.dst_cloud,
                                                                                      input_info='storage_info')

        act_network_trans = networks_transporter.NetworkTransporter(self.src_cloud, self.dst_cloud)


        namespace_scheduler = namespace.Namespace()

        task_ident_trans = act_identity_trans

        task_images_trans = act_get_info_images >> act_deploy_images

        task_stop_vms = act_stop_vms

        # task_convert_c_to_v_to_i = act_convert_c_to_v >> act_convert_v_to_i
        # task_convert_i_to_v_to_c = act_convert_i_to_v >> act_convert_v_to_c
        # task_transport_volumes = task_convert_c_to_v_to_i >> act_copy_g2g_vols >> task_convert_i_to_v_to_c
        task_get_inst_vol_info = act_convert_c_to_v >> act_rename_inst_vol_src
        task_deploy_inst_vol = act_deploy_inst_volumes >> act_rename_inst_vol_dst
        task_transfer_inst_vol_data = act_inst_vol_data_map >> act_inst_vol_transport_data

        task_transport_inst_volumes = task_get_inst_vol_info \
                                 >> task_deploy_inst_vol >> task_transfer_inst_vol_data >> act_convert_v_to_c

        task_attaching_volumes = act_attaching

        task_get_inst_info = act_get_info_inst

        task_inst_trans = act_comp_res_trans >> act_conv_comp_img >> \
                          act_copy_inst_images >> act_conv_image_comp >> \
                          act_net_prep >> act_map_com_info >> act_deploy_instances

        task_get_info_available_volumes = act_get__available_vol_info >> act_rename_available_vol_src
        task_deploy_available_vol = act_deploy_available_volumes >> act_rename_available_vol_dst
        task_transfer_available_vol_data = act_available_vol_data_map >> act_available_vol_transport_data

        task_transport_available_volumes = task_get_info_available_volumes >> \
                                           task_deploy_available_vol >> task_transfer_available_vol_data

        task_networking_trans = act_network_trans

        # process_migration = task_ident_trans >> task_images_trans >> \
        #                     task_transport_available_volumes >> task_get_inst_info >> \
        #                     task_stop_vms >> task_transport_inst_volumes >> \
        #                     task_inst_trans >> task_attaching_volumes


        process_migration = task_ident_trans >> act_network_trans >> \
                            task_get_inst_info >> task_stop_vms >> \
                            task_inst_trans

        process_migration = cursor.Cursor(process_migration)
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, cursor=process_migration)
        scheduler_migr.start()