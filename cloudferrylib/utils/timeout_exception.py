__author__ = 'toha'


class TimeoutException(Exception):
    def __init__(self, status_obj, exp_status, msg):
        self.status_obj = status_obj
        self.exp_status = exp_status
        self.msg = msg
