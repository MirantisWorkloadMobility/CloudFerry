import logging
import sys
import time
import random
import string
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
import json
from fabric.api import local, run
import os
import yaml
import inspect

__author__ = 'mirrorcoder'

ISCSI = "iscsi"
CEPH = "ceph"
BOOT_FROM_VOLUME = "boot_volume"
BOOT_FROM_IMAGE = "boot_image"
ANY = "any"
NO = "no"
EPHEMERAL = "ephemeral"
REMOTE_FILE = "remote file"
QCOW2 = "qcow2"
YES = "yes"
NAME_LOG_FILE = 'migrate.log'


def dump_to_file(path, snapshot):
    with open(path, "w+") as f:
        json.dump(convert_to_dict(snapshot), f)


def load_json_from_file(file_path):
    f = open(file_path, 'r')
    return json.load(f)

primitive = [int, long, bool, float, type(None), str, unicode]


def convert_to_dict(obj, ident=0, limit_ident=8):
    ident += 1
    if type(obj) in primitive:
        return obj
    if isinstance(obj, inspect.types.InstanceType) or (type(obj) not in (list, tuple, dict)):
        if ident <= limit_ident:
            try:
                obj = obj.convert_to_dict()
            except AttributeError as e:
                try:
                    t = obj.__dict__
                    t['_type_class'] = str(obj.__class__)
                    obj = t
                except AttributeError as e:
                    return str(obj.__class__ if hasattr(obj, '__class__') else type(obj))
        else:
            return str(obj.__class__)
    if type(obj) is dict:
        res = {}
        for item in obj:
            if ident <= limit_ident:
                res[item] = convert_to_dict(obj[item], ident)
            else:
                res[item] = str(obj[item])
        return res
    if type(obj) in (list, tuple):
        res = []
        for item in obj:
            if ident <= limit_ident:
                res.append(convert_to_dict(item, ident))
            else:
                res.append(str(item))
        return res if type(obj) is list else tuple(res)


def convert_to_obj(obj, restore_object, namespace):
    if type(obj) in primitive:
        return obj
    if type(obj) is dict:
        for item in obj:
            obj[item] = convert_to_obj(obj[item], restore_object, namespace)
        obj = restore_object.restore(obj, namespace)
    if type(obj) in (list, tuple):
        res = []
        for item in obj:
            res.append(convert_to_obj(item, restore_object, namespace))
        obj = res if type(obj) is list else tuple(res)
    return obj


class GeneratorPassword:
    def __init__(self, length=7):
        self.length = length
        self.chars = string.ascii_letters + string.digits + '@#$%&*'

    def get_random_password(self):
        return self.__generate_password()

    def __generate_password(self):
        random.seed = (os.urandom(1024))
        return ''.join(random.choice(self.chars) for i in range(self.length))


class Postman:
    def __init__(self, username, password, from_addr, mail_server):
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.mail_server = mail_server

    def __enter__(self):
        self.server = smtplib.SMTP(self.mail_server)
        self.server.ehlo()
        self.server.starttls()
        self.server.login(self.username, self.password)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.server.quit()

    def send(self, to, subject, msg):
        msg_mime = MIMEMultipart('alternative')
        msg_mime.attach(MIMEText(msg, 'html'))
        msg_mime['Subject'] = subject
        msg_mime['From'] = self.from_addr
        msg_mime['To'] = to
        self.server.sendmail(self.from_addr, to, msg_mime.as_string())

    def close(self):
        self.server.quit()


class Templater:
    def render(self, name_file, args):
        temp_file = open(name_file, 'r')
        temp_render = temp_file.read()
        for arg in args:
            temp_render = temp_render.replace("{{%s}}" % arg, args[arg])
        temp_file.close()
        return temp_render


def get_log(name):
    LOG = logging.getLogger(name)
    LOG.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s : %(message)s')
    hdlr = logging.FileHandler(NAME_LOG_FILE)
    hdlr.setFormatter(formatter)
    LOG.addHandler(hdlr)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter_out = logging.Formatter('%(asctime)s: %(message)s')
    ch.setFormatter(formatter_out)
    LOG.addHandler(ch)
    return LOG


class StackCallFunctions(object):
    def __init__(self):
        self.stack_call_functions = []
        self.listeners = []

    def trigger(self, name_event):
        for listener in self.listeners:
            {
                'func_enter': listener.func_enter,
                'func_exit': listener.func_exit
            }[name_event](self)

    def append(self, func_name, args, kwargs):
        self.stack_call_functions.append({
            'func_name': func_name,
            'args': args,
            'kwargs': kwargs
        })
        self.trigger('func_enter')

    def depth(self):
        return len(self.stack_call_functions)

    def pop(self, res):
        self.stack_call_functions[-1]['result'] = res
        self.trigger('func_exit')
        self.stack_call_functions.pop()

    def addListener(self, listener):
        self.listeners.insert(0, listener)

    def removeListenerLast(self):
        self.listeners = self.listeners[1:]


stack_call_functions = StackCallFunctions()


def log_step(log):
    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            stack_call_functions.append(func.__name__, args, kwargs)
            log.info("%s> Step %s" % ("- - "*stack_call_functions.depth(), func.__name__))
            res = func(*args, **kwargs)
            stack_call_functions.pop(res)
            return res
        return inner
    return decorator


class forward_agent:

    """
        Forwarding ssh-key for access on to source and destination clouds via ssh
    """

    def __init__(self, key_file):
        self.key_file = key_file

    def __enter__(self):
        info_agent = local("eval `ssh-agent` && echo $SSH_AUTH_SOCK && ssh-add %s" %
                           (self.key_file), capture=True).split("\n")
        self.pid = info_agent[0].split(" ")[-1]
        self.ssh_auth_sock = info_agent[1]
        os.environ["SSH_AGENT_PID"] = self.pid
        os.environ["SSH_AUTH_SOCK"] = self.ssh_auth_sock

    def __exit__(self, type, value, traceback):
        local("kill -9 %s"%(self.pid))
        del os.environ["SSH_AGENT_PID"]
        del os.environ["SSH_AUTH_SOCK"]


class up_ssh_tunnel:

    """
        Up ssh tunnel on dest controller node for transferring data
    """

    def __init__(self, address_dest_compute, address_dest_controller, ssh_port=9999):
        self.address_dest_compute = address_dest_compute
        self.address_dest_controller = address_dest_controller
        self.ssh_port = ssh_port
        self.cmd = "ssh -oStrictHostKeyChecking=no -L %s:%s:22 -R %s:localhost:%s %s -Nf"

    def __enter__(self):
        run(self.cmd % (self.ssh_port, self.address_dest_compute, self.ssh_port, self.ssh_port,
                        self.address_dest_controller) + " && sleep 2")

    def __exit__(self, type, value, traceback):
        run(("pkill -f '"+self.cmd+"'") % (self.ssh_port, self.address_dest_compute, self.ssh_port, self.ssh_port,
                                           self.address_dest_controller))
        time.sleep(2)


class ChecksumImageInvalid(Exception):
    def __init__(self, checksum_source, checksum_dest):
        self.checksum_source = checksum_source
        self.checksum_dest = checksum_dest

    def __str__(self):
        return repr("Checksum of image source = %s Checksum of image dest = %s" %
                    (self.checksum_source, self.checksum_dest))

