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


from cloudferrylib.base import storage
from cinderclient.v1 import client as cinder_client
from fabric.api import settings
from fabric.api import run

AVAILABLE = 'available'
IN_USE = "in-use"

class CinderStorage(storage.Storage):

    """
    The main class for working with Openstack cinder client
    """

    def __init__(self, config):
        self.cinder_client = self.get_cinder_client(self.config)
        super(CinderStorage, self).__init__(config)

    def get_cinder_client(self, params):

        """ Getting cinder client """

        return cinder_client.Client(params["user"],
                                    params["password"],
                                    params["tenant"],
                                    "http://%s:35357/v2.0/" % params["host"])

    def read_info(self, opts={}):
        info = dict(resource=self, storage={})
        info['volumes'] = []
        for vol in self.get_volumes_list(search_opts=opts):
            volume = {
                'id': vol.id,
                'size': vol.size,
                'name': vol.name,
                'description': vol.description,
                'volume_type': vol.volume_type,
                'availability_zone': vol.availability_zone,
                'device': vol.attachments[0]['device'],
                'bootable': vol.bootable,
            }
            info['storage']['volumes'].append({'volume': volume,
                                               'meta': {
                                                   'image': None
                                               }})
        return info

    def convert(self, vol):
        info = {
            'size': vol['volume']['size'],
            'display_name': vol['volume']['name'],
            'display_description': vol['volume']['description'],
            'volume_type': vol['volume']['volume_type'],
            'availability_zone': vol['volume']['availability_zone'],
        }
        if 'image' in vol['meta']:
            if vol['meta']['image']:
                info['imageRef'] = vol['meta']['image']['id']
        return info

    def deploy(self, info):
        volumes = []
        for vol in info['storage']['volumes']:
            vol_for_deploy = self.convert(vol['volume'])
            volume = self.create_volume(**vol_for_deploy)
            self.wait_for_status(volume.id, AVAILABLE)
            self.attach_volume_to_instance(volume, vol)
            volumes.append(volume)
        return volumes

    def attach_volume_to_instance(self, volume, volume_info):
        if 'instance' in volume_info['meta']:
            if volume_info['meta']['instance']:
                self.attach_volume(volume.id, volume_info['meta']['instance']['id'], volume_info['volume']['device'])
                self.wait_for_status(volume.id, IN_USE)

    def get_volumes_list(self, detailed=True, search_opts=None):
        return self.cinder_client.volumes.list(detailed, search_opts)

    def create_volume(self, size, **kwargs):
        return self.cinder_client.volumes.create(size, **kwargs)

    def delete_volume(self, volume_id):
        volume = self.__get_volume_by_id(volume_id)
        self.cinder_client.volumes.delete(volume)

    def __get_volume_by_id(self, volume_id):
        return self.cinder_client.volumes.get(volume_id)

    def update_volume(self, volume_id, **kwargs):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.update(volume, **kwargs)

    def attach_volume(self, volume_id, instance_id, mountpoint, mode='rw'):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.attach(volume,
                                                 instance_uuid=instance_id,
                                                 mountpoint=mountpoint,
                                                 mode=mode)

    def detach_volume(self, volume_id):
        return self.cinder_client.volumes.detach(volume_id)

    def finish(self, vol_id, meta):
        self.__patch_option_bootable_of_volume(vol_id, meta['volume'].bootable)

    def __patch_option_bootable_of_volume(self, volume_id, bootable):
        cmd = 'use cinder;update volumes set volumes.bootable=%s where volumes.id="%s"' % (int(bootable), volume_id)
        self.__cmd_mysql_on_dest_controller(cmd)

    def __cmd_mysql_on_dest_controller(self, cmd):
        with settings(host_string=self.config['host']):
            run('mysql %s %s -e \'%s\'' % (("-u "+self.config['mysql']['user'])
                                           if self.config['mysql']['user'] else "",
                                           "-p"+self.config['mysql']['password']
                                           if self.config['mysql']['password'] else "",
                                           cmd))

    def upload_volume_to_image(self, volume_id, force, image_name,
                               container_format, disk_format):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.upload_to_image(
            volume=volume,
            force=force,
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format)
