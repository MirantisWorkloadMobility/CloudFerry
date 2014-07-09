__author__ = 'mirrorcoder'


class FileLikeProxy:
    def __init__(self, transfer_object, callback):
        self.__callback = callback
        self.resp = transfer_object.get_ref_image()
        self.length = self.resp.length if self.resp.length else transfer_object.get_info_image().size
        self.id = transfer_object.get_info_image().id
        self.name = transfer_object.get_info_image().name
        self.percent = self.length / 100
        self.res = 0
        self.delta = 0

    def read(self, *args, **kwargs):
        res = self.resp.read(*args, **kwargs)
        self.__trigger_callback(len(res))
        return res

    def __trigger_callback(self, len_data):
        self.delta += len_data
        self.res += len_data
        if self.delta > self.percent:
            self.__callback(self.res, self.length, self.id, self.name)
            self.delta = 0

    def close(self):
        self.resp.close()

    def isclosed(self):
        return self.resp.isclosed()

    def begin(self):
        return self.resp.begin()

    def getheader(self, *args, **kwargs):
        res = self.resp.getheader(*args, **kwargs)
        return res

