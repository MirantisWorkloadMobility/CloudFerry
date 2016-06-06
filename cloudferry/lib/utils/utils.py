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
import threading
import timeit
import random
import re
import string
import os

from fabric.api import settings, local, env, sudo
from fabric.context_managers import hide
import yaml

LOG = logging.getLogger(__name__)

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


class GeneratorPassword(object):
    def __init__(self, length=7):
        self.length = length
        self.chars = string.ascii_letters + string.digits + '@#$%&*'

    def get_random_password(self):
        return self.__generate_password()

    def __generate_password(self):
        return ''.join(random.choice(self.chars) for i in range(self.length))


class Templater(object):
    def render(self, name_file, args):
        temp_file = open(name_file, 'r')
        temp_render = temp_file.read()
        for arg in args:
            temp_render = temp_render.replace("{{%s}}" % arg, args[arg])
        temp_file.close()
        return temp_render


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


def get_disk_path(instance, blk_list, disk=DISK):
    LOG.debug("get_disk_path: instance='%s', blk_list='%s', disk='%s'",
              instance.id, blk_list, disk)
    disk_path = None
    disk = "/" + disk
    for i in blk_list:
        if instance.id + disk == i[-(LEN_UUID_INSTANCE + len(disk)):]:
            disk_path = i
        if instance.name + disk == i[-(len(instance.name) + len(disk)):]:
            disk_path = i
    LOG.debug('get_disk_path: disk_path=%s', disk_path)
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


def qualname(cls):
    """
    Returns fully qualified name of class (something like
    package_name.module_name.ClassName)
    :param cls: class object
    :return: string representing fully qualified name
    """
    return cls.__module__ + '.' + cls.__name__


class ThreadLocalStorage(object):
    def __init__(self, **defaults):
        self._tls = threading.local()
        self._defaults = defaults

    def __getattr__(self, item):
        return getattr(self._tls, item, self._defaults.get(item))

    def __setattr__(self, key, value):
        if key in ('_tls', '_defaults'):
            super(ThreadLocalStorage, self).__setattr__(key, value)
        return setattr(self._tls, key, value)
