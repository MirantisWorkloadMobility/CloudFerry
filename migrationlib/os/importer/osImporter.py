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

from migrationlib.os import osCommon
from osBuilderImporter import osBuilderImporter
from utils import ChecksumImageInvalid, ISCSI, CEPH, BOOT_FROM_IMAGE, \
    BOOT_FROM_VOLUME, ANY, NO, EPHEMERAL, REMOTE_FILE, YES, log_step, get_log


LOG = get_log(__name__)


class MultiCaseAlgorithm:
    def __init__(self, mode_boot,
                 backend_cinder_dest,
                 ephemeral_back_source,
                 is_ephemeral_disk):
        self.mode_boot = mode_boot
        self.backend_cinder_dest = backend_cinder_dest
        self.ephemeral_back_source = ephemeral_back_source
        self.is_ephemeral_disk = is_ephemeral_disk

    def __hash__(self):
        return hash((self.mode_boot,
                     self.backend_cinder_dest,
                     self.ephemeral_back_source,
                     self.is_ephemeral_disk))

    def __eq__(self, other):
        return hash(self) == hash(other)


class Importer(osCommon.osCommon):
    def __init__(self, config):
        self.config = config['clouds']['destination']
        self.config_from = config['clouds']['source']
        super(Importer, self).__init__(self.config)

    def clean_cloud(self, delete_images=False):
        for inst in self.nova_client.servers.list():
            inst.delete()
        for volume in self.cinder_client.volumes.list():
            volume.force_delete()
        if delete_images:
            for image in self.glance_client.images.list():
                self.glance_client.images.delete(image.id)

    @log_step(LOG)
    def upload(self, data):

        """
        The main method for data uploading from source cloud
        """
        builderImporter = osBuilderImporter(self.keystone_client,
                                            self.glance_client,
                                            self.cinder_client,
                                            self.nova_client,
                                            self.network_client,
                                            self.config,
                                            self.config_from,
                                            data)
        return self.get_algorithm_import(data)(builderImporter)

    @log_step(LOG)
    def get_algorithm_import(self, data):
        return {
            # mode_boot, backend_cinder_dest, ephemeral_back_source, is_ephemeral_disk
            MultiCaseAlgorithm(BOOT_FROM_IMAGE, ISCSI, REMOTE_FILE, NO): self.__upload_iscsi_backend,
            MultiCaseAlgorithm(BOOT_FROM_IMAGE, CEPH, REMOTE_FILE, NO): self.__upload_ceph_backend,
            MultiCaseAlgorithm(BOOT_FROM_IMAGE, ISCSI, REMOTE_FILE, YES): self.__upload_iscsi_backend_ephemeral,
            MultiCaseAlgorithm(BOOT_FROM_IMAGE, CEPH, REMOTE_FILE, YES): self.__upload_ceph_backend_ephemeral,
            MultiCaseAlgorithm(BOOT_FROM_IMAGE, ANY, CEPH, YES): self.__upload_ephemeral_on_ceph,
            MultiCaseAlgorithm(BOOT_FROM_IMAGE, ANY, CEPH, NO): self.__upload_ephemeral_on_ceph_without_disk,
            MultiCaseAlgorithm(BOOT_FROM_VOLUME, ANY, ANY, NO): self.__upload_boot_volume,
            MultiCaseAlgorithm(BOOT_FROM_VOLUME, ANY, ANY, YES): self.__upload_boot_volume_with_ephem_disk
        }[self.__detect_algorithm_upload(self.config, data)]

    @log_step(LOG)
    def __detect_algorithm_upload(self, config, data):
        mode_boot = self.__detect_mode_boot(data)
        ephemeral = self.__is_ephemeral(data)
        backend_ephemeral = self.__detect_backend_ephemeral(data)
        backend_cinder = self.__detect_backend_cinder(config) if backend_ephemeral != CEPH else ANY
        if mode_boot == BOOT_FROM_VOLUME:
            return MultiCaseAlgorithm(BOOT_FROM_VOLUME, ANY, ANY, ephemeral)
        else:
            return MultiCaseAlgorithm(BOOT_FROM_IMAGE, backend_cinder, backend_ephemeral, ephemeral)

    def __detect_backend_ephemeral(self, data):
        if data['disk']['type'] == CEPH:
            return CEPH
        else:
            return REMOTE_FILE

    def __is_ephemeral(self, data):
        return YES if data["disk"]["ephemeral"] else NO

    def __detect_backend_cinder(self, config):
        return ISCSI if config['cinder']['backend'] == ISCSI else CEPH

    def __detect_mode_boot(self, data):
        if data["boot_from_volume"]:
            return BOOT_FROM_VOLUME
        else:
            return BOOT_FROM_IMAGE

    @log_step(LOG)
    def __upload_ceph_backend(self, builderImporter):

        """
        Algorithm of migrationlib for ceph destination backend for cinder
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .merge_delta_and_image()\
            .create_instance()\
            .import_volumes()

    @log_step(LOG)
    def __upload_iscsi_backend(self, builderImporter):
        """
        Algorithm of migrationlib for iscsi-like destination backend for cinder
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .stop_instance()\
            .import_delta_file()\
            .import_volumes()\
            .start_instance()

    @log_step(LOG)
    def __upload_ceph_backend_ephemeral(self, builderImporter):

        """
        Algorithm of migrationlib for ceph destination backend for cinder and ephemeral drive
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .merge_delta_and_image()\
            .create_instance()\
            .stop_instance()\
            .import_ephemeral_drive()\
            .start_instance()\
            .import_volumes()


    @log_step(LOG)
    def __upload_iscsi_backend_ephemeral(self, builderImporter):
        """
        Algorithm of migrationlib for iscsi-like destination backend for cinder and ephemeral drive
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .stop_instance()\
            .import_delta_file()\
            .import_ephemeral_drive()\
            .import_volumes()\
            .start_instance()

    @log_step(LOG)
    def __upload_boot_volume(self, builderImporter):
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .prepare_for_boot_volume()\
            .create_instance()\
            .stop_instance()\
            .import_volumes()\
            .start_instance()\
            .delete_image_from_source_and_dest_cloud()

    @log_step(LOG)
    def __upload_boot_volume_with_ephem_disk(self, builderImporter):
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .prepare_for_boot_volume()\
            .create_instance()\
            .stop_instance()\
            .import_ephemeral_drive()\
            .start_instance()\
            .import_volumes()\
            .delete_image_from_source_and_dest_cloud()

    @log_step(LOG)
    def __upload_ephemeral_on_ceph(self, builderImporter):
        """
        Algorithm of migrationlib for iscsi-like destination backend for cinder and ephemeral drive
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .stop_instance()\
            .import_ephemeral_drive()\
            .start_instance()\
            .import_volumes()

    @log_step(LOG)
    def __upload_ephemeral_on_ceph_without_disk(self, builderImporter):
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .import_volumes()
