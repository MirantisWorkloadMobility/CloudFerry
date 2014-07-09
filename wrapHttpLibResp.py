
__author__ = 'mirrorcoder'


class WrapHttpLibResp:
    def __init__(self, resp, callback, id, name):
        self.resp = resp
        self.__callback = callback
        self.percent = self.resp.length / 100
        self.res = 0
        self.delta = 0
        self.length = self.resp.length
        self.id = id
        self.name = name

    def read(self, *args, **kwargs):
        res = self.resp.read(*args, **kwargs)
        len_data = len(res)
        self.delta += len_data
        self.res += len_data
        if self.delta > self.percent:
            self.__callback(self.res, self.length, self.id, self.name)
            self.delta = 0
        return res

    def close(self):
        self.resp.close()

    def isclosed(self):
        return self.resp.isclosed()

    def begin(self):
        return self.resp.begin()

    def getheader(self, *args, **kwargs):
        res = self.resp.getheader(*args, **kwargs)
        return res

