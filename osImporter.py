import osCommon
import logging
from utils import ChecksumImageInvalid, ISCSI, CEPH, BOOT_FROM_IMAGE, \
    BOOT_FROM_VOLUME, ANY, NOT_EPHEMERAL, EPHEMERAL, REMOTE_FILE
from osBuilderImporter import osBuilderImporter

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('importer.log')
LOG.addHandler(hdlr)


class MultiCaseAlgorithm:
    def __init__(self, mode_boot,
                 backend_cinder_dest,
                 ephemeral_back_source):
        self.mode_boot = mode_boot
        self.backend_cinder_dest = backend_cinder_dest
        self.ephemeral_back_source = ephemeral_back_source

    def __hash__(self):
        return hash((self.mode_boot,
                     self.backend_cinder_dest,
                     self.ephemeral_back_source))

    def __eq__(self, other):
        return hash(self) == hash(other)


class Importer(osCommon.osCommon):
    def __init__(self, config):
        self.config = config['clouds']['to']
        self.config_from = config['clouds']['from']
        super(Importer, self).__init__(self.config)

    def clean_cloud(self, delete_images=False):
        for inst in self.nova_client.servers.list():
            inst.delete()
        for volume in self.cinder_client.volumes.list():
            volume.force_delete()
        if delete_images:
            for image in self.glance_client.images.list():
                self.glance_client.images.delete(image.id)

    def upload(self, data):

        """
        The main method for data uploading from source cloud
        """
        LOG.info("Start migrate instance")
        builderImporter = osBuilderImporter(self.glance_client,
                                            self.cinder_client,
                                            self.nova_client,
                                            self.network_client,
                                            self.config,
                                            self.config_from,
                                            data)
        try:
            new_instance = {
                # mode_boot, backend_cinder_dest, ephemeral_back_dest, ephemeral_back_source
                MultiCaseAlgorithm(BOOT_FROM_IMAGE, ISCSI, NOT_EPHEMERAL): self.__upload_iscsi_backend,
                MultiCaseAlgorithm(BOOT_FROM_IMAGE, CEPH, NOT_EPHEMERAL): self.__upload_ceph_backend,
                MultiCaseAlgorithm(BOOT_FROM_IMAGE, ISCSI, REMOTE_FILE): self.__upload_iscsi_backend_ephemeral,
                MultiCaseAlgorithm(BOOT_FROM_IMAGE, CEPH, REMOTE_FILE): self.__upload_ceph_backend_ephemeral,
                MultiCaseAlgorithm(BOOT_FROM_IMAGE, ANY, CEPH): self.__upload_ephemeral_on_ceph,
                MultiCaseAlgorithm(BOOT_FROM_VOLUME, ANY, NOT_EPHEMERAL): self.__upload_boot_volume,
            }[self.__detect_algorithm_upload(data)](builderImporter)
            LOG.info("New instance on destantion cloud %s" % new_instance)
        except ChecksumImageInvalid as e:
            LOG.error(e)

    def __detect_algorithm_upload(self, data):
        mode_boot = self.__detect_mode_boot(data)
        ephemeral = self.__detect_backend_ephemeral(data) if self.__is_ephemeral(data) == EPHEMERAL else NOT_EPHEMERAL
        backend_cinder = self.__detect_backend_cinder() if ephemeral != CEPH else ANY
        if mode_boot == BOOT_FROM_VOLUME:
            return MultiCaseAlgorithm(BOOT_FROM_VOLUME, ANY, NOT_EPHEMERAL)
        else:
            return MultiCaseAlgorithm(BOOT_FROM_IMAGE, backend_cinder, ephemeral)

    def __detect_backend_ephemeral(self, data):
        if data['disk']['type'] == CEPH:
            return CEPH
        else:
            return REMOTE_FILE

    def __is_ephemeral(self, data):
        return EPHEMERAL if data["disk"]["ephemeral"] else NOT_EPHEMERAL

    def __detect_backend_cinder(self):
        return ISCSI if self.config['cinder']['backend'] == ISCSI else CEPH

    def __detect_mode_boot(self, data):
        if data["boot_from_volume"]:
            return BOOT_FROM_VOLUME
        else:
            return BOOT_FROM_IMAGE

    def __upload_ceph_backend(self, builderImporter):

        """
        Algorithm of migration for ceph destination backend for cinder
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .merge_delta_and_image()\
            .create_instance()\
            .import_volumes()\
            .finish()

    def __upload_iscsi_backend(self, builderImporter):
        """
        Algorithm of migration for iscsi-like destination backend for cinder
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .stop_instance()\
            .import_delta_file()\
            .start_instance()\
            .import_volumes()\
            .finish()

    def __upload_ceph_backend_ephemeral(self, builderImporter):

        """
        Algorithm of migration for ceph destination backend for cinder and ephemeral drive
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .merge_delta_and_image()\
            .create_instance()\
            .stop_instance()\
            .import_ephemeral_drive()\
            .start_instance()\
            .import_volumes()\
            .finish()

    def __upload_iscsi_backend_ephemeral(self, builderImporter):
        """
        Algorithm of migration for iscsi-like destination backend for cinder and ephemeral drive
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .stop_instance()\
            .import_delta_file()\
            .import_ephemeral_drive()\
            .start_instance()\
            .import_volumes()\
            .finish()

    def __upload_boot_volume(self, builderImporter):
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .prepare_for_boot_volume()\
            .create_instance()\
            .import_volumes()\
            .delete_image_from_source_and_dest_cloud()\
            .finish()

    def __upload_ephemeral_on_ceph(self, builderImporter):
        """
        Algorithm of migration for iscsi-like destination backend for cinder and ephemeral drive
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .stop_instance()\
            .import_ephemeral_drive()\
            .start_instance()\
            .import_volumes()\
            .finish()
