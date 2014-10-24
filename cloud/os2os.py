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

from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import get_info_images
from cloudferrylib.os.actions import get_info_volumes
from cloudferrylib.os.actions import identity_transporter
from cloudferrylib.os.actions import get_info_volumes
from cloudferrylib.os.actions import converter_image_to_volume
from cloudferrylib.os.actions import converter_volume_to_image


class OS2OSFerry(cloud_ferry.CloudFerry):

    def __init__(self, config):
        super(OS2OSFerry, self). __init__(config)
        resources = {'identity': keystone.KeystoneIdentity,
                     'image': glance_image.GlanceImage,
                     'storage': cinder_storage.CinderStorage
                     }
        self.src_cloud = cloud.Cloud(resources, cloud.SRC, config)
        self.dst_cloud = cloud.Cloud(resources, cloud.DST, config)
        
    def migrate(self):
        #action1 = get_info_volumes.GetInfoVolumes(self.src_cloud)
        #action2 = converter_volume_to_image.ConverterVolumeToImage("qcow2", self.src_cloud)
        #action3 = copy_g2g.CopyFromGlanceToGlance()
        #data = action1.run()
        #images = action2.run(data['storage_data'])
        #action3.run(self.src_cloud, self.dst_cloud)
        #transporter = identity_transporter.IdentityTransporter()
        #transporter.run(self.src_cloud, self.dst_cloud)
        #
        #action_get_im = get_info_images.GetInfoImages(self.src_cloud)
        #images_info = action_get_im.run(image_name='cirros_image')
        #
        #action_copy_im = copy_g2g.CopyFromGlanceToGlance(self.src_cloud,
        #                                                 self.dst_cloud)
        #new_info = action_copy_im.run()
        #print new_info

        action1 = get_info_volumes.GetInfoVolumes(self.src_cloud)
        volumes_info = action1.run()
        #volumes_info['storage_data']['storage']['volumes'].pop('b9f3a274-1025-444e-9a2b-24f8deabd629')

        action2 = converter_volume_to_image.ConverterVolumeToImage(
            "qcow2",
            self.src_cloud)
        images = action2.run(volumes_info['storage_data'])

        action3 = copy_g2g.CopyFromGlanceToGlance(self.src_cloud,
                                                  self.dst_cloud)

        new_info = action3.run(image_info=images)

        action4 = converter_image_to_volume.ConverterImageToVolume()
        new_vol_info = action4.run(images_info=new_info,
                                   cloud_current=self.dst_cloud)

        print new_vol_info
