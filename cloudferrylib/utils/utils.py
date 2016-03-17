# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.

import logging
import time
import timeit
import random
import re
import string
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
import json
import os
import inspect
from multiprocessing import Lock

from jinja2 import Environment, FileSystemLoader
from fabric.api import run, settings, local, env, sudo
from fabric.context_managers import hide
import yaml

LOG = logging.getLogger(__name__)

ISCSI = "iscsi"
CEPH = "ceph"
BOOT_FROM_VOLUME = "boot_volume"
BOOT_FROM_IMAGE = "boot_image"
ANY = "any"
NO = "no"
EPHEMERAL = "ephemeral"
REMOTE_FILE = "remote file"
QCOW2 = "qcow2"
RAW = "raw"
YES = "yes"
PATH_TO_SNAPSHOTS = 'snapshots'
AVAILABLE = 'available'
IN_USE = 'in-use'
STATUS = 'status'

DISK = "disk"
DISK_EPHEM = "disk.local"
DISK_CONFIG = "disk.config"
LEN_UUID_INSTANCE = 36

HOST_SRC = 'host_src'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
PATH_DST = 'path_dst'

STORAGE_RESOURCE = 'storage'
VOLUMES_TYPE = 'volumes'
VOLUME_BODY = 'volume'
VOLUMES_DB = 'volumes_db'
SNAPSHOTS = 'snapshots'

OBJSTORAGE_RESOURCE = 'objstorage'
CONTAINERS = 'containers'
CONTAINER_BODY = 'container'

COMPUTE_RESOURCE = 'compute'
INSTANCES_TYPE = 'instances'
INSTANCE_BODY = 'instance'

NETWORK_RESOURCE = 'network'
NETWORKS_TYPE = 'networks'
NETWORK_BODY = 'network'

DIFF_BODY = 'diff'
EPHEMERAL_BODY = 'ephemeral'

INTERFACES = 'interfaces'

IMAGE_RESOURCE = 'image'
IMAGES_TYPE = 'images'
IMAGE_BODY = 'image'

IDENTITY_RESOURCE = 'identity'
TENANTS_TYPE = 'tenants'
USERS_TYPE = 'users'
IGNORE = 'ignore'

RESOURCE_TYPES = {
    STORAGE_RESOURCE: VOLUMES_TYPE,
    COMPUTE_RESOURCE: INSTANCES_TYPE,
    NETWORK_RESOURCE: NETWORKS_TYPE,
    IMAGE_RESOURCE: IMAGES_TYPE,
    OBJSTORAGE_RESOURCE: CONTAINERS,
    IDENTITY_RESOURCE: TENANTS_TYPE,
}

META_INFO = 'meta'
OLD_ID = 'old_id'

FILTER_PATH = 'configs/filter.yaml'

up_ssh_tunnel = None

SSH_CMD = \
    "ssh -oStrictHostKeyChecking=no -L %s:%s:22 -R %s:localhost:%s %s -Nf"

SSH_KEY_LIST_RE = re.compile(r'^\d+ [^ ]+ (?P<key_file>.+) [^ ]+$')


class ext_dict(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError("Exporter has no attribute %s" % name)


def get_snapshots_list_repository(path=PATH_TO_SNAPSHOTS):
    path_source = path + '/source'
    path_dest = path + '/dest'
    s = os.listdir(path_source)
    s.sort()
    source = [{'path': '%s/%s' % (path_source, f),
               'timestamp': f.replace(".snapshot", "")} for f in s]
    d = os.listdir(path_dest)
    d.sort()
    dest = [{'path': '%s/%s' % (path_dest, f),
             'timestamp': f.replace(".snapshot", "")} for f in d]
    return {
        'source': source,
        'dest': dest
    }


def dump_to_file(path, snapshot):
    with open(path, "w+") as f:
        json.dump(convert_to_dict(snapshot), f)


def load_json_from_file(file_path):
    f = open(file_path, 'r')
    return json.load(f)

primitive = [int, long, bool, float, type(None), str, unicode]


def convert_to_dict(obj, ident=0, limit_ident=6):
    ident += 1
    if type(obj) in primitive:
        return obj
    if isinstance(obj, inspect.types.InstanceType) or \
            (type(obj) not in (list, tuple, dict)):
        if ident <= limit_ident:
            try:
                obj = obj.convert_to_dict()
            except AttributeError:
                try:
                    t = obj.__dict__
                    t['_type_class'] = str(obj.__class__)
                    obj = t
                except AttributeError:
                    return str(obj.__class__ if hasattr(obj, '__class__')
                               else type(obj))
        else:
            return str(obj.__class__ if hasattr(obj, '__class__')
                       else type(obj))
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
            log.info("%s> Step %s" % ("- - " * stack_call_functions.depth(),
                                      func.__name__))
            res = func(*args, **kwargs)
            stack_call_functions.pop(res)
            return res
        return inner
    return decorator


class forward_agent(object):
    """
        Forwarding ssh-key for access on to source and
        destination clouds via ssh
    """

    def __init__(self, key_files):
        self.key_files = key_files

    def __enter__(self):
        ensure_ssh_key_added(self.key_files)

    def __exit__(self, type, value, traceback):
        # never kill previously started ssh-agent, so that user only has to
        # enter private key password once
        pass


def ensure_ssh_key_added(key_files):
    need_adding = set(os.path.abspath(os.path.expanduser(p))
                      for p in key_files)
    with settings(hide('warnings', 'running', 'stdout', 'stderr'),
                  warn_only=True):
        # First check already added keys
        res = local("ssh-add -l", capture=True)
        if res.succeeded:
            for line in res.splitlines():
                m = SSH_KEY_LIST_RE.match(line)
                if not m:
                    continue
                path = os.path.abspath(os.path.expanduser(m.group('key_file')))
                need_adding.discard(path)

    with settings(hide('warnings', 'running', 'stdout', 'stderr')):
        # Next add missing keys
        if need_adding:
            key_string = ' '.join(need_adding)
            start_ssh_agent = ("eval `ssh-agent` && echo $SSH_AUTH_SOCK && "
                               "ssh-add %s") % key_string
            info_agent = local(start_ssh_agent, capture=True).splitlines()
            os.environ["SSH_AGENT_PID"] = info_agent[0].split()[-1]
            os.environ["SSH_AUTH_SOCK"] = info_agent[1]
            return False
        else:
            return True


class wrapper_singletone_ssh_tunnel:

    def __init__(self, interval_ssh="9000-9999", locker=Lock()):
        self.interval_ssh = [int(interval_ssh.split('-')[0]),
                             int(interval_ssh.split('-')[1])]
        self.busy_port = []
        self.locker = locker

    def get_free_port(self):
        with self.locker:
            beg = self.interval_ssh[0]
            end = self.interval_ssh[1]
            while beg <= end:
                if beg not in self.busy_port:
                    self.busy_port.append(beg)
                    return beg
                beg += 1
        raise RuntimeError("No free ssh port")

    def free_port(self, port):
        with self.locker:
            if port in self.busy_port:
                self.busy_port.remove(port)

    def __call__(self, address_dest_compute, address_dest_controller, host,
                 **kwargs):
        return UpSshTunnelClass(address_dest_compute,
                                address_dest_controller,
                                host,
                                self.get_free_port,
                                self.free_port)


class UpSshTunnelClass:

    """
        Up ssh tunnel on dest controller node for transferring data
    """

    def __init__(self, address_dest_compute, address_dest_controller, host,
                 callback_get, callback_free):
        self.address_dest_compute = address_dest_compute
        self.address_dest_controller = address_dest_controller
        self.get_free_port = callback_get
        self.remove_port = callback_free
        self.host = host
        self.cmd = SSH_CMD

    def __enter__(self):
        self.port = self.get_free_port()
        with settings(host_string=self.host,
                      connection_attempts=env.connection_attempts):
            run(self.cmd % (self.port,
                            self.address_dest_compute,
                            self.port,
                            self.port,
                            self.address_dest_controller) + " && sleep 2")
        return self.port

    def __exit__(self, type, value, traceback):
        with settings(host_string=self.host,
                      connection_attempts=env.connection_attempts):
            run(("pkill -f '" + self.cmd + "'") %
                (self.port,
                 self.address_dest_compute,
                 self.port,
                 self.port,
                 self.address_dest_controller))
        time.sleep(2)
        self.remove_port(self.port)


def render_info(info_values, template_path="templates",
                template_file="info.html"):
    info_env = Environment(loader=FileSystemLoader(template_path))
    template = info_env.get_template(template_file)
    return template.render(info_values)


def write_info(rendered_info, info_file="source_info.html"):
    with open(info_file, "wb") as ifile:
        ifile.write(rendered_info)


def libvirt_instance_exists(libvirt_name, init_host, compute_host, ssh_user,
                            ssh_sudo_password):
    with settings(host_string=compute_host,
                  user=ssh_user,
                  password=ssh_sudo_password,
                  gateway=init_host,
                  connection_attempts=env.connection_attempts,
                  warn_only=True,
                  quiet=True):
        command = 'virsh domid %s' % libvirt_name
        LOG.debug('[%s] Running command %s', compute_host, command)
        out = sudo(command)
        LOG.debug('[%s] Result of running %s: %s', compute_host, command, out)
        return out.succeeded


def get_libvirt_block_info(libvirt_name, init_host, compute_host, ssh_user,
                           ssh_sudo_password):
    with settings(host_string=compute_host,
                  user=ssh_user,
                  password=ssh_sudo_password,
                  gateway=init_host,
                  connection_attempts=env.connection_attempts):
        command = "virsh domblklist %s" % libvirt_name
        LOG.debug('[%s] Running command %s', compute_host, command)
        out = sudo(command)
        LOG.debug('[%s] Result of running %s: %s', compute_host, command, out)
        libvirt_output = out.split()
    return libvirt_output


def find_element_by_in(list_values, word):
    for i in list_values:
        if word in i:
            return i


def init_singletones(cfg):
    globals()['up_ssh_tunnel'] = wrapper_singletone_ssh_tunnel(
        cfg.migrate.ssh_transfer_port)


def get_disk_path(instance, blk_list, is_ceph_ephemeral=False, disk=DISK):
    disk_path = None
    if not is_ceph_ephemeral:
        disk = "/" + disk
        for i in blk_list:
            if instance.id + disk == i[-(LEN_UUID_INSTANCE + len(disk)):]:
                disk_path = i
            if instance.name + disk == i[-(len(instance.name) + len(disk)):]:
                disk_path = i
    else:
        disk = "_" + disk
        for i in blk_list:
            if ("compute/%s%s" % (instance.id, disk)) == i:
                disk_path = i
    return disk_path


def check_file(file_path):
    return file_path is not None and os.path.isfile(file_path)


def read_yaml_file(yaml_file_path):
    if not check_file(yaml_file_path):
        return None
    with open(yaml_file_path) as yfile:
        return yaml.load(yfile)


def write_yaml_file(file_name, content):
    with open(file_name, 'w') as yfile:
        yaml.safe_dump(content, yfile)


def timer(func, *args, **kwargs):
    t = timeit.Timer(lambda: func(*args, **kwargs))
    elapsed = t.timeit(number=1)
    return elapsed


def import_class_by_string(name):
    """ This function takes string in format
        'cloudferrylib.os.storage.cinder_storage.CinderStorage'
        And returns class object"""
    module, class_name = name.split('.')[:-1], name.split('.')[-1]
    mod = __import__(".".join(module))
    for comp in module[1:]:
        mod = getattr(mod, comp)
    return getattr(mod, class_name)
