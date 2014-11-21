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
from cloudferrylib.os.actions import attach_used_volumes_via_nova
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import convert_image_to_compute
from cloudferrylib.os.actions import convert_image_to_volume
from cloudferrylib.os.actions import convert_compute_to_image
from cloudferrylib.os.actions import convert_compute_to_volume
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import convert_volume_to_compute
from cloudferrylib.os.actions import create_reference
from cloudferrylib.os.actions import prepare_volumes_data_map
from cloudferrylib.os.actions import transport_ceph_to_ceph_via_ssh
from cloudferrylib.os.actions import get_info_instances
from cloudferrylib.os.actions import prepare_networks
from cloudferrylib.os.actions import start_vm
from cloudferrylib.scheduler import task
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

        # Available volumes migration only (both ceph cases)

        act_ident_trans = identity_transporter.IdentityTransporter(self.src_cloud, self.dst_cloud)
        act_get_vol_info = get_info_volumes.GetInfoVolumes(self.src_cloud,
                                                           search_opts={utl.STATUS: utl.AVAILABLE})
        act_deploy_vol = deploy_volumes.DeployVolumes(self.dst_cloud)
        act_rename_vol_src = create_reference.CreateReference('storage_info',
        'src_storage_info')
        act_rename_vol_dst = create_reference.CreateReference('storage_info',
        'dst_storage_info')
        act_vol_data_map = prepare_volumes_data_map.PrepareVolumesDataMap('src_storage_info',
        'dst_storage_info')
        act_transport_data = transport_ceph_to_ceph_via_ssh.TransportCephToCephViaSsh(self.config,
                                                                                      self.src_cloud,
                                                                                      self.dst_cloud,
                                                                                      input_info='storage_info')

        namespace_scheduler = namespace.Namespace()

        task_identity_transfer = act_ident_trans
        task_get_vol_info = act_get_vol_info >> act_rename_vol_src
        task_deploy_vol = act_deploy_vol >> act_rename_vol_dst
        task_transfer_vol_data = act_vol_data_map >> act_transport_data

        process_migration = task_identity_transfer >> task_get_vol_info >> task_deploy_vol >> task_transfer_vol_data
        process_migration = cursor.Cursor(process_migration)

        scheduler_migr = scheduler.Scheduler(namespace=namespace_scheduler, cursor=process_migration)
        scheduler_migr.start()

