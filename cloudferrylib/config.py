# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import contextlib
import logging

from cloudferrylib.os import clients, consts
from cloudferrylib.utils import bases
from cloudferrylib.utils import remote
from cloudferrylib.utils import utils

LOG = logging.getLogger(__name__)
MODEL_LIST = [
    'cloudferrylib.os.discovery.keystone.Tenant',
    'cloudferrylib.os.discovery.glance.Image',
    'cloudferrylib.os.discovery.cinder.Volume',
    'cloudferrylib.os.discovery.nova.Server',
]


class SshSettings(bases.Hashable, bases.Representable):
    def __init__(self, username, sudo_password=None, gateway=None,
                 connection_attempts=1, cipher=None, key_file=None):
        self.username = username
        self.sudo_password = sudo_password
        self.gateway = gateway
        self.connection_attempts = connection_attempts
        self.cipher = cipher
        self.key_file = key_file


class Configuration(bases.Hashable, bases.Representable):
    def __init__(self, clouds=None):
        self.clouds = {}
        for name, cloud in (clouds or {}).items():
            credential = Credential(**cloud['credential'])
            scope = Scope(**cloud['scope'])
            ssh_settings = SshSettings(**cloud['ssh'])
            self.clouds[name] = OpenstackCloud(name, credential, scope,
                                               ssh_settings)

    def get_cloud(self, name):
        return self.clouds[name]


class Scope(bases.Hashable, bases.Representable):
    def __init__(self, project_id=None, project_name=None, domain_id=None):
        self.project_name = project_name
        self.project_id = project_id
        self.domain_id = domain_id


class Credential(bases.Hashable, bases.Representable):
    def __init__(self, auth_url, username, password,
                 region_name=None, domain_id=None,
                 https_insecure=False, https_cacert=None,
                 endpoint_type=consts.EndpointType.ADMIN):
        self.auth_url = auth_url
        self.username = username
        self.password = password
        self.region_name = region_name
        self.domain_id = domain_id
        self.https_insecure = https_insecure
        self.https_cacert = https_cacert
        self.endpoint_type = endpoint_type


class OpenstackCloud(object):
    def __init__(self, name, credential, scope, ssh_settings, discover=None):
        if discover is None:
            discover = MODEL_LIST
        self.name = name
        self.credential = credential
        self.scope = scope
        self.ssh_settings = ssh_settings
        self.discover = discover

    def image_client(self, scope=None):
        return clients.image_client(self.credential, scope or self.scope)

    def identity_client(self, scope=None):
        return clients.identity_client(self.credential, scope or self.scope)

    def volume_client(self, scope=None):
        return clients.volume_client(self.credential, scope or self.scope)

    def compute_client(self, scope=None):
        return clients.compute_client(self.credential, scope or self.scope)

    @contextlib.contextmanager
    def remote_executor(self, hostname, key_file=None, ignore_errors=False):
        key_files = []
        settings = self.ssh_settings
        if settings.key_file is not None:
            key_files.append(settings.key_file)
        if key_file is not None:
            key_files.append(key_file)
        if key_files:
            utils.ensure_ssh_key_added(key_files)
        try:
            yield remote.RemoteExecutor(
                hostname, settings.username,
                sudo_password=settings.sudo_password,
                gateway=settings.gateway,
                connection_attempts=settings.connection_attempts,
                cipher=settings.cipher,
                key_file=settings.key_file,
                ignore_errors=ignore_errors)
        finally:
            remote.RemoteExecutor.close_connection(hostname)
