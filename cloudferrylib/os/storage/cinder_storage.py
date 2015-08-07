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


import time

from cinderclient.v1 import client as cinder_client

from cloudferrylib.base import storage
from cloudferrylib.utils import mysql_connector
from cloudferrylib.utils import utils as utl

LOG = utl.get_log(__name__)

AVAILABLE = 'available'
IN_USE = "in-use"


class CinderStorage(storage.Storage):

    """
    The main class for working with Openstack cinder client
    """

    def __init__(self, config, cloud):
        self.config = config
        self.host = config.cloud.host
        self.mysql_host = config.mysql.host \
            if config.mysql.host else self.host
        self.cloud = cloud
        self.identity_client = cloud.resources[utl.IDENTITY_RESOURCE]
        self.mysql_connector = self.get_db_connection()
        super(CinderStorage, self).__init__(config)

    @property
    def cinder_client(self):
        return self.proxy(self.get_client(self.config), self.config)

    def get_client(self, params=None):

        """ Getting cinder client """

        params = self.config if not params else params

        return cinder_client.Client(
            params.cloud.user,
            params.cloud.password,
            params.cloud.tenant,
            params.cloud.auth_url)

    def get_db_connection(self):
        if not hasattr(self.cloud.config, self.cloud.position + '_storage'):
            LOG.debug('Running on default storage settings')
            return mysql_connector.MysqlConnector(self.config.mysql, 'cinder')
        else:
            LOG.debug('Running on custom storage settings')
            my_settings = getattr(self.cloud.config,
                                  self.cloud.position + '_storage')
            return mysql_connector.MysqlConnector(my_settings,
                                                  my_settings.database_name)

    def read_info(self, **kwargs):
        info = {utl.VOLUMES_TYPE: {}}
        for vol in self.get_volumes_list(search_opts=kwargs):
            volume = self.convert_volume(vol, self.config, self.cloud)
            snapshots = {}
            if self.config.migrate.keep_volume_snapshots:
                search_opts = {'volume_id': volume['id']}
                for snap in self.get_snapshots_list(search_opts=search_opts):
                    snapshot = self.convert_snapshot(snap,
                                                     volume,
                                                     self.config,
                                                     self.cloud)
                    snapshots[snapshot['id']] = snapshot
            info[utl.VOLUMES_TYPE][vol.id] = {utl.VOLUME_BODY: volume,
                                              'snapshots': snapshots,
                                              utl.META_INFO: {
                                              }}
        if self.config.migrate.keep_volume_storage:
            info['volumes_db'] = {utl.VOLUMES_TYPE: '/tmp/volumes'}

            # cleanup db
            self.cloud.ssh_util.execute('rm -rf /tmp/volumes',
                                        host_exec=self.mysql_host)

            for table_name, file_name in info['volumes_db'].iteritems():
                self.download_table_from_db_to_file(table_name, file_name)
        return info

    def deploy(self, info):
        if info.get('volumes_db'):
            return self.deploy_volumes_db(info)
        return self.deploy_volumes(info)

    def attach_volume_to_instance(self, volume_info):
        if 'instance' in volume_info[utl.META_INFO]:
            if volume_info[utl.META_INFO]['instance']:
                self.attach_volume(
                    volume_info[utl.VOLUME_BODY]['id'],
                    volume_info[utl.META_INFO]['instance']['instance']['id'],
                    volume_info[utl.VOLUME_BODY]['device'])

    def get_volumes_list(self, detailed=True, search_opts=None):
        search_opts['all_tenants'] = 1
        return self.cinder_client.volumes.list(detailed, search_opts)

    def get_snapshots_list(self, detailed=True, search_opts=None):
        return self.cinder_client.volume_snapshots.list(detailed, search_opts)

    def create_snapshot(self, volume_id, force=False,
                        display_name=None, display_description=None):
        return self.cinder_client.volume_snapshots.create(volume_id,
                                                          force,
                                                          display_name,
                                                          display_description)

    def create_volume(self, size, **kwargs):
        return self.cinder_client.volumes.create(size, **kwargs)

    def delete_volume(self, volume_id):
        volume = self.get_volume_by_id(volume_id)
        self.cinder_client.volumes.delete(volume)

    def get_volume_by_id(self, volume_id):
        return self.cinder_client.volumes.get(volume_id)

    def update_volume(self, volume_id, **kwargs):
        volume = self.get_volume_by_id(volume_id)
        return self.cinder_client.volumes.update(volume, **kwargs)

    def attach_volume(self, volume_id, instance_id, mountpoint, mode='rw'):
        volume = self.get_volume_by_id(volume_id)
        return self.cinder_client.volumes.attach(volume,
                                                 instance_uuid=instance_id,
                                                 mountpoint=mountpoint,
                                                 mode=mode)

    def detach_volume(self, volume_id):
        return self.cinder_client.volumes.detach(volume_id)

    def finish(self, vol):
        self.__patch_option_bootable_of_volume(
            vol[utl.VOLUME_BODY]['id'],
            vol[utl.VOLUME_BODY]['bootable'])

    def upload_volume_to_image(self, volume_id, force, image_name,
                               container_format, disk_format):
        volume = self.get_volume_by_id(volume_id)
        resp, image = self.cinder_client.volumes.upload_to_image(
            volume=volume,
            force=force,
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format)
        return resp, image['os-volume_upload_image']['image_id']

    def get_status(self, resource_id):
        return self.cinder_client.volumes.get(resource_id).status

    def wait_for_status(self, resource_id, status, limit_retry=60):
        counter = 0
        while self.get_status(resource_id) != status and counter < limit_retry:
            time.sleep(1)
            counter += 1

        if counter == limit_retry:
            LOG.warning("Volume '%s' has not changed status to '%s'",
                        resource_id, status)

    def deploy_volumes(self, info):
        new_ids = {}
        # if info.get('volumes_db'):
        #     return self.deploy_volumes_db(info)
        for vol_id, vol in info[utl.VOLUMES_TYPE].iteritems():
            vol_for_deploy = self.convert_to_params(vol)
            volume = self.create_volume(**vol_for_deploy)
            vol[utl.VOLUME_BODY]['id'] = volume.id
            self.wait_for_status(volume.id, AVAILABLE)
            self.finish(vol)
            new_ids[volume.id] = vol_id
        return new_ids

    def deploy_volumes_db(self, info):
        for table_name, file_name in info['volumes_db'].iteritems():
            self.upload_table_to_db(table_name, file_name)
        for tenant in info['tenants']:
            self.update_column_with_condition('volumes',
                                              'project_id',
                                              tenant['tenant']['id'],
                                              tenant[utl.META_INFO]['new_id'])
        for user in info['users']:
            self.update_column_with_condition('volumes', 'user_id',
                                              user['user']['id'],
                                              user[utl.META_INFO]['new_id'])
        self.update_column_with_condition('volumes', 'attach_status',
                                          'attached', 'detached')
        self.update_column_with_condition('volumes', 'status', 'in-use',
                                          'available')
        self.update_column('volumes', 'instance_uuid', 'NULL')
        return {}

    @staticmethod
    def convert_volume(vol, cfg, cloud):
        compute = cloud.resources[utl.COMPUTE_RESOURCE]
        volume = {
            'id': vol.id,
            'size': vol.size,
            'display_name': vol.display_name,
            'display_description': vol.display_description,
            'volume_type': (
                None if vol.volume_type == u'None' else vol.volume_type),
            'availability_zone': vol.availability_zone,
            'device': vol.attachments[0][
                'device'] if vol.attachments else None,
            'bootable': False,
            'volume_image_metadata': {},
            'host': None,
            'path': None
        }
        if 'bootable' in vol.__dict__:
            volume[
                'bootable'] = True if vol.bootable.lower() == 'true' else False
        if 'volume_image_metadata' in vol.__dict__:
            volume['volume_image_metadata'] = {
                'image_id': vol.volume_image_metadata['image_id'],
                'checksum': vol.volume_image_metadata['checksum']
            }
        if cfg.storage.backend == utl.CEPH:
            volume['path'] = "%s/%s%s" % (
                cfg.storage.rbd_pool, cfg.storage.volume_name_template, vol.id)
            volume['host'] = (cfg.storage.host
                              if cfg.storage.host
                              else cfg.cloud.host)
        elif vol.attachments and (cfg.storage.backend == utl.ISCSI):
            instance = compute.read_info(
                search_opts={'id': vol.attachments[0]['server_id']})
            instance = instance[utl.INSTANCES_TYPE]
            instance_info = instance.values()[0][utl.INSTANCE_BODY]
            volume['host'] = instance_info['host']
            list_disk = utl.get_libvirt_block_info(
                instance_info['instance_name'],
                cloud.getIpSsh(),
                instance_info['host'],
                cfg.cloud.ssh_user,
                cfg.cloud.ssh_sudo_password)
            volume['path'] = utl.find_element_by_in(list_disk, vol.id)
        return volume

    @staticmethod
    def convert_snapshot(snap, volume, cfg, cloud):

        snapshot = {
            'id': snap.id,
            'volume_id': snap.volume_id,
            'tenant_id': snap.project_id,
            'display_name': snap.display_name,
            'display_description': snap.display_description,
            'created_at': snap.created_at,
            'size': snap.size,
            'vol_path': volume['path']
        }

        if cfg.storage.backend == utl.CEPH:
            snapshot['name'] = "%s%s" % (cfg.storage.snapshot_name_template,
                                         snap.id)
            snapshot['path'] = "%s@%s" % (snapshot['vol_path'],
                                          snapshot['name'])
            snapshot['host'] = (cfg.storage.host
                                if cfg.storage.host
                                else cfg.cloud.host)

        return snapshot

    @staticmethod
    def convert_to_params(vol):
        info = {
            'size': vol[utl.VOLUME_BODY]['size'],
            'display_name': vol[utl.VOLUME_BODY]['display_name'],
            'display_description': vol[utl.VOLUME_BODY]['display_description'],
            'volume_type': vol[utl.VOLUME_BODY]['volume_type'],
            'availability_zone': vol[utl.VOLUME_BODY]['availability_zone'],
        }
        if 'image' in vol[utl.META_INFO]:
            if vol[utl.META_INFO]['image']:
                info['imageRef'] = vol[utl.META_INFO]['image']['id']
        return info

    def __patch_option_bootable_of_volume(self, volume_id, bootable):
        cmd = ('UPDATE volumes SET volumes.bootable=%s WHERE '
               'volumes.id="%s"') % (int(bootable), volume_id)
        self.mysql_connector.execute(cmd)

    def download_table_from_db_to_file(self, table_name, file_name):
        self.mysql_connector.execute("SELECT * FROM %s INTO OUTFILE '%s';" %
                                     (table_name, file_name))

    def upload_table_to_db(self, table_name, file_name):
        self.mysql_connector.execute("LOAD DATA INFILE '%s' INTO TABLE %s" %
                                     (file_name, table_name))

    def update_column_with_condition(self, table_name, column,
                                     old_value, new_value):

        self.mysql_connector.execute("UPDATE %s SET %s='%s' WHERE %s='%s'" %
                                     (table_name, column, new_value, column,
                                         old_value))

    def update_column(self, table_name, column_name, new_value):
        self.mysql_connector.execute("UPDATE %s SET %s='%s'" %
                                     (table_name, column_name, new_value))

    def get_volume_path_iscsi(self, vol_id):
        cmd = "SELECT provider_location FROM volumes WHERE id='%s';" % vol_id

        result = self.cloud.mysql_connector.execute(cmd)

        if not result:
            raise Exception('There is no such raw in Cinder DB with the '
                            'specified volume_id=%s' % vol_id)

        provider_location = result.fetchone()[0]
        provider_location_list = provider_location.split()

        iscsi_target_id = provider_location_list[1]
        lun = provider_location_list[2]
        ip = provider_location_list[0].split(',')[0]

        volume_path = '/dev/disk/by-path/ip-%s-iscsi-%s-lun-%s' % (
            ip,
            iscsi_target_id,
            lun)

        return volume_path
