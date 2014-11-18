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
from cloudferrylib.os.identity import keystone
from cloudferrylib.os.network import neutron
from cloudferrylib.os.compute import nova_compute
from cloudferrylib.os.actions import prepare_networks
from cloudferrylib.os.actions import get_info_volumes
from cloudferrylib.os.actions import transport_instance
from cloudferrylib.os.actions import transport_db_via_ssh
from cloudferrylib.os.actions import detach_used_volumes
from cloudferrylib.os.actions import attach_used_volumes
from cloudferrylib.os.actions import attach_used_volumes_via_nova
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import convert_image_to_compute
from cloudferrylib.os.actions import convert_image_to_volume
from cloudferrylib.os.actions import convert_compute_to_image
from cloudferrylib.os.actions import convert_compute_to_volume
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import convert_volume_to_compute
from cloudferrylib.os.actions import get_info_instances
from cloudferrylib.os.actions import start_vm
from cloudferrylib.utils import utils as utl


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
        act_get_info = get_info_instances.GetInfoInstances(self.src_cloud)
        act_convert_c_to_i = convert_compute_to_image.ConvertComputeToImage(self.config, self.src_cloud)
        act_copy_g2g_vols = copy_g2g.CopyFromGlanceToGlance(self.src_cloud, self.dst_cloud)
        act_copy_g2g_imgs = copy_g2g.CopyFromGlanceToGlance(self.src_cloud, self.dst_cloud)
        act_convert_i_to_c = convert_image_to_compute.ConvertImageToCompute()
        act_convert_c_to_v = convert_compute_to_volume.ConvertComputeToVolume(self.config, self.src_cloud)
        act_convert_c_to_v_attach = convert_compute_to_volume.ConvertComputeToVolume(self.config, self.src_cloud)
        act_convert_v_to_i = convert_volume_to_image.ConvertVolumeToImage('qcow2', self.src_cloud)
        act_convert_i_to_v = convert_image_to_volume.ConvertImageToVolume(self.dst_cloud)
        act_convert_v_to_c = convert_volume_to_compute.ConvertVolumeToCompute(self.src_cloud, self.dst_cloud)
        act_attaching = attach_used_volumes_via_nova.AttachVolumesNova(self.dst_cloud)
        act_prep_net = prepare_networks.PrepareNetworks(self.dst_cloud, self.config)
        action2 = transport_instance.TransportInstance(self.config, self.src_cloud, self.dst_cloud)
        act_start_vm = start_vm.StartVms(self.dst_cloud)

        namespace_scheduler = namespace.Namespace()

        task_convert_c_to_v_to_i = act_convert_c_to_v >> act_convert_v_to_i
        task_convert_i_to_v_to_c = act_convert_i_to_v >> act_convert_v_to_c
        task_transport_volumes = task_convert_c_to_v_to_i >> act_copy_g2g_vols >> task_convert_i_to_v_to_c
        task_transport_images = act_convert_c_to_i >> act_copy_g2g_imgs >> act_convert_i_to_c
        task_transport_instances = act_prep_net >> action2 >> act_start_vm
        task_attaching_volumes = act_convert_c_to_v_attach >> act_attaching
        transport_resources = task_transport_volumes >> task_transport_images
        process_migration = act_identity_trans >> act_get_info >> transport_resources >> task_transport_instances >> task_attaching_volumes

        process_migration = cursor.Cursor(process_migration)
        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, cursor=process_migration)
        scheduler_migr.start()
