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
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import convert_image_to_compute
from cloudferrylib.os.actions import convert_compute_to_image
from cloudferrylib.os.actions import get_info_instances
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

        # action1 = identity_transporter.IdentityTransporter()
        # info_identity = action1.run(self.src_cloud, self.dst_cloud)['info_identity']
        act_get_info = get_info_instances.GetInfoInstances(self.src_cloud)
        act_convert_c_to_i = convert_compute_to_image.ConvertComputeToImage(self.config, self.src_cloud)
        act_copy_g2g = copy_g2g.CopyFromGlanceToGlance(self.src_cloud, self.dst_cloud)
        act_convert_i_to_c = convert_image_to_compute.ConvertImageToCompute()
        act_prep_net = prepare_networks.PrepareNetworks(self.dst_cloud, self.config)
        action2 = transport_instance.TransportInstance()

        info = act_get_info.run()['info']
        images_info = act_convert_c_to_i.run(info=info)['images_info']
        images_info = act_copy_g2g.run(images_info=images_info)['images_info']
        info = act_convert_i_to_c.run(images_info=images_info)['info']
        info = act_prep_net.run(info)['info']
        info = action2.run(self.config, self.src_cloud, self.dst_cloud, info)






