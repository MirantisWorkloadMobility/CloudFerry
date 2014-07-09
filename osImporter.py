import osCommon
import logging
from utils import ChecksumImageInvalid
from osBuilderImporter import osBuilderImporter

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('importer.log')
LOG.addHandler(hdlr)

ISCSI = "iscsi"
CEPH = "ceph"
BOOT_FROM_VOLUME = "boot_volume"
BOOT_FROM_IMAGE = "boot_image"


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
                                            self.neutron_client,
                                            self.config,
                                            self.config_from,
                                            data)
        try:
            new_instance = {
                ISCSI: self.__upload_iscsi_backend,
                CEPH: self.__upload_ceph_backend,
                BOOT_FROM_VOLUME: self.__upload_boot_volume
            }[self.__detect_algorithm_upload(data)](builderImporter)
            LOG.info("New instance on destantion cloud %s" % new_instance)
        except ChecksumImageInvalid as e:
            LOG.error(e)

    def __detect_algorithm_upload(self, data):
        mode_boot = self.__detect_mode_boot(data)
        if mode_boot == BOOT_FROM_VOLUME:
            return BOOT_FROM_VOLUME
        return self.__detect_backend_glance()

    def __detect_backend_glance(self):
        return self.config['glance']['backend']

    def __detect_mode_boot(self, data):
        if data["boot_from_volume"]:
            return BOOT_FROM_VOLUME
        else:
            return BOOT_FROM_IMAGE

    def __upload_ceph_backend(self, builderImporter):

        """
        Algorithm of migration for ceph destination backend for glance
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .merge_delta_and_image()\
            .create_instance()\
            .import_volumes()\
            .finish()

    def __upload_iscsi_backend(self, builderImporter):
        """
        Algorithm of migration for iscsi-like destination backend for glance
        """
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .import_instance_delta()\
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