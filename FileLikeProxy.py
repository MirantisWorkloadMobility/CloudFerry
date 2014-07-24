import time
import re
__author__ = 'mirrorcoder'

# Maximum Bytes Per Packet
CHUNK_SIZE = 512 * 1024 #B


class FileLikeProxy:
    def __init__(self, transfer_object, callback, speed_limit = '1mb'):
        self.__callback = callback
        self.resp = transfer_object.get_ref_image()
        self.length = self.resp.length if self.resp.length else transfer_object.get_info_image().size
        self.id = transfer_object.get_info_image().id
        self.name = transfer_object.get_info_image().name
        self.percent = self.length / 100
        self.res = 0
        self.delta = 0
        self.buffer = ''
        self.prev_send_time = 0
        self.speed_limit = self.__parse_speed_limit(speed_limit)
        if self.speed_limit != 0:
            self.read = self.speed_limited_read


    def __parse_speed_limit(self, speed_limit):
        if speed_limit is '-':
            return 0
        array = filter(None, re.split(r'(\d+)', speed_limit))
        mult = {
           'b' : 1,
           'kb' : 1024,
           'mb' : 1024 * 1024,
        }[array[1].lower()]
        return int(array[0]) * mult

    def read(self, *args, **kwargs):
        res = self.resp.read(*args, **kwargs)
        self.__trigger_callback(len(res))
        return res

    def speed_limited_read(self, *args, **kwargs):
        if len(self.buffer) < CHUNK_SIZE:
            self.buffer += self.resp.read(*args, **kwargs)

        res = self.buffer[0:CHUNK_SIZE]
        self.buffer = self.buffer[CHUNK_SIZE::]

        self.__trigger_callback(len(res))
        cur_send_time = time.time()
        sleep_time = float(len(res)) / self.speed_limit
        sleep_time -= cur_send_time - self.prev_send_time
        time.sleep(max( (0, sleep_time) ))
        self.prev_send_time = cur_send_time
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

