__author__ = 'mirrorcoder'


class VolumeTransfer:
    """ The main class for gathering information for volumes migrationlib"""
    def __init__(self, volume, instance, image_id, glance_client):
        self.id = volume.id
        self.size = volume.size
        self.name = volume.display_name
        self.description = volume.display_description
        self.volume_type = None if volume.volume_type == u'None' else volume.volume_type
        self.availability_zone = volume.availability_zone
        self.device = volume.attachments[0]['device']
        self.host = getattr(instance, 'OS-EXT-SRV-ATTR:host')
        self.image_id = image_id
        self.bootable = True if volume.bootable == 'true' else False
        self.glance_client = glance_client
        self.__info = self.glance_client.images.get(self.image_id)
        self.checksum = self.__info.checksum

    def get_info_image(self):
        return self.__info

    def get_ref_image(self):
        """
        return file-like object which will be using on destination cloud for importing images (aka volumes)
        """
        resp = self.glance_client.images.data(self.image_id)._resp
        return resp

    def delete(self):
        self.glance_client.images.delete(self.image_id)

    def convert_to_dict(self):
        return {
            '_type_class': VolumeTransfer.__name__,
            'id': self.id,
            'size': self.size,
            'name': self.name,
            'description': self.description,
            'volume_type': self.volume_type,
            'availability_zone': self.availability_zone,
            'device': self.device,
            'host': self.host,
            'image_id': self.image_id,
            'bootable': self.bootable
        }