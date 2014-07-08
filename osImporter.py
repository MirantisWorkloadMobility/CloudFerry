import osCommon
import logging
from utils import ChecksumImageInvalid
from osBuilderImporter import osBuilderImporter

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
hdlr = logging.FileHandler('importer.log')
LOG.addHandler(hdlr)


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
        LOG.info("Start migrate instance")
        builderImporter = osBuilderImporter(self.glance_client,
                                            self.cinder_client,
                                            self.nova_client,
                                            self.quantum_client,
                                            self.config,
                                            self.config_from,
                                            data)
        try:
            new_instance = {
                'iscsi': self.__upload_iscsi_backend,
                'ceph': self.__upload_ceph_backend
            }[self.__detect_backend_glance()](builderImporter)
            LOG.info("New instance on destantion cloud %s" % new_instance)
        except ChecksumImageInvalid as e:
            LOG.error(e)

    def __detect_backend_glance(self):
        return self.config['glance']['backend']

    def __upload_ceph_backend(self, builderImporter):
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .merge_delta_and_image()\
            .create_instance()\
            .import_volumes()\
            .finish()

    def __upload_iscsi_backend(self, builderImporter):
        return builderImporter\
            .prepare_for_creating_new_instance()\
            .create_instance()\
            .import_instance_delta()\
            .import_volumes()\
            .finish()

