__author__ = 'mirrorcoder'


class ImageTransfer:

    def __init__(self, image_id, glance_client):
        self.glance_client = glance_client
        self.image_id = image_id
        self.__info = self.glance_client.images.get(image_id)
        self.checksum = self.__info.checksum

    def get_info_image(self):
        return self.__info

    def get_ref_image(self):
        return self.glance_client.images.data(self.image_id)._resp

    def delete(self):
        self.glance_client.images.delete(self.image_id)

    def convert_to_dict(self):
        return {
            '_type_class': ImageTransfer.__name__,
            'image_id': self.image_id
        }