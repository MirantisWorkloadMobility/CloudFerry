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
import re
import threading

from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v2_0 import client as v2_0_client
from novaclient.v1_1 import client as nova
from neutronclient.v2_0 import client as neutron
from glanceclient.v1 import client as glance
from cinderclient.v2 import client as cinder

from cloudferrylib.os import consts
from cloudferrylib.utils import proxy_client

_lock = threading.Lock()
_tokens = {}
_endpoints = {}


class ClientProxy(object):
    def __init__(self, factory_fn, credential, scope, token=None,
                 endpoint=None, path=None, service_type=None):
        if path is None:
            path = []
        if token is None and endpoint is None:
            assert service_type is not None
            token = _get_token(credential, scope)
            endpoint = _get_endpoint(credential, scope, service_type)
        else:
            assert token is not None and endpoint is not None
        self._factory_fn = factory_fn
        self._credential = credential
        self._scope = scope
        self._token = token
        self._endpoint = endpoint
        self._path = path

    def __getattr__(self, name):
        new_path = list(self._path)
        new_path.append(name)
        attr = self._get_attr(new_path)
        if hasattr(attr, '__call__') or proxy_client.is_wrapping(attr):
            return ClientProxy(self._factory_fn, self._credential, self._scope,
                               self._token, self._endpoint, new_path)
        else:
            return attr

    def __call__(self, *args, **kwargs):
        # pylint: disable=broad-except
        for retry in (True, False):
            try:
                method = self._get_attr(self._path)
                return method(*args, **kwargs)
            except Exception as ex:
                http_status = getattr(ex, 'http_status', None)
                if retry and http_status in (401, 403):
                    discard_token(self._token)
                else:
                    raise

    def _get_attr(self, path):
        current = self._factory_fn(self._token, self._endpoint)
        for element in path:
            current = getattr(current, element)
        return current


def _get_authenticated_v2_client(credential, scope):
    client = v2_0_client.Client(auth_url=credential.auth_url,
                                username=credential.username,
                                password=credential.password,
                                region_name=credential.region_name,
                                domain_id=credential.domain_id,
                                endpoint_type=credential.endpoint_type,
                                insecure=credential.https_insecure,
                                cacert=credential.https_cacert,
                                project_domain_id=scope.domain_id,
                                project_name=scope.project_name,
                                project_id=scope.project_id,
                                tenant_id=scope.project_id)
    if client.auth_ref is None:
        client.authenticate()
    return client


def _get_token(credential, scope):
    # TODO(antonf): make it so get_token for one set of creds don't block
    # TODO(antonf): get_token for other set of creds
    with _lock:
        token_key = (credential, scope)
        token = _tokens.get(token_key)
        if token is None:
            # TODO(antonf): add support for Keystone v3 API
            client = _get_authenticated_v2_client(credential, scope)
            new_token = client.auth_token
            for service_type in consts.ServiceType.values():
                try:
                    service_url = client.service_catalog.url_for(
                        service_type=service_type,
                        endpoint_type=credential.endpoint_type,
                        region_name=credential.region_name)
                    _endpoints[credential, scope, service_type] = service_url
                except ks_exceptions.EndpointNotFound:
                    continue
            _tokens[token_key] = new_token
            _tokens[new_token] = token_key
            if token in _tokens:
                del _tokens[token]
            token = new_token
        return token


def _get_endpoint(credential, scope, service_type):
    with _lock:
        return _endpoints[credential, scope, service_type]


def discard_token(token):
    with _lock:
        try:
            key = _tokens.pop(token)
            if _tokens[key] == token:
                del _tokens[key]
        except KeyError:
            pass


def identity_client(credential, scope):
    def factory_fn(token, endpoint):
        return v2_0_client.Client(token=token,
                                  endpoint=endpoint,
                                  endpoint_override=endpoint,
                                  insecure=credential.https_insecure,
                                  cacert=credential.https_cacert)
    return ClientProxy(factory_fn, credential, scope,
                       service_type=consts.ServiceType.IDENTITY)


def compute_client(credential, scope):
    def factory_fn(token, endpoint):
        client = nova.Client(auth_token=token,
                             insecure=credential.https_insecure,
                             cacert=credential.https_cacert)
        client.set_management_url(endpoint)
        return client

    return ClientProxy(factory_fn, credential, scope,
                       service_type=consts.ServiceType.COMPUTE)


def network_client(credential, scope):
    def factory_fn(token, endpoint):
        return neutron.Client(token=token,
                              endpoint_url=endpoint,
                              insecure=credential.https_insecure,
                              cacert=credential.https_cacert)

    return ClientProxy(factory_fn, credential, scope,
                       service_type=consts.ServiceType.NETWORK)


def image_client(credential, scope):
    def factory_fn(token, endpoint):
        endpoint = re.sub(r'v(\d)/?$', '', endpoint)
        return glance.Client(endpoint=endpoint,
                             token=token,
                             insecure=credential.https_insecure,
                             cacert=credential.https_cacert)

    return ClientProxy(factory_fn, credential, scope,
                       service_type=consts.ServiceType.IMAGE)


def volume_client(credential, scope):
    def factory_fn(token, endpoint):
        client = cinder.Client(insecure=credential.https_insecure,
                               cacert=credential.https_cacert)
        client.client.management_url = endpoint
        client.client.auth_token = token
        return client

    return ClientProxy(factory_fn, credential, scope,
                       service_type=consts.ServiceType.VOLUME)
