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
import logging
import re
import time
import threading
import traceback

from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v2_0 import client as v2_0_client
from novaclient.v2 import client as nova
from neutronclient.v2_0 import client as neutron
from glanceclient.v1 import client as glance
from cinderclient.v1 import client as cinder

from cloudferry.lib.os import consts
from cloudferry.lib.utils import proxy_client
from cloudferry.lib.utils import retrying

LOG = logging.getLogger(__name__)
_lock = threading.Lock()
_tokens = {}
_endpoints = {}


class ClientProxy(object):
    def __init__(self, factory_fn, cloud, credential, scope,
                 path=None, service_type=None):
        if path is None:
            path = []
        self._factory_fn = factory_fn
        self._cloud = cloud
        self._credential = credential
        self._scope = scope
        self._path = path
        self._service_type = service_type

    def __getattr__(self, name):
        new_path = list(self._path)
        new_path.append(name)
        attr = self._get_attr(new_path, 'token', 'http://endpoint')
        if hasattr(attr, '__call__') or proxy_client.is_wrapping(attr):
            return ClientProxy(self._factory_fn, self._cloud, self._credential,
                               self._scope, new_path, self._service_type)
        else:
            return attr

    def __call__(self, *args, **kwargs):
        # pylint: disable=broad-except
        token = get_token(self._credential, self._scope)
        endpoint = get_endpoint(self._credential, self._scope,
                                self._service_type)
        for do_retry in (True, False):
            try:
                LOG.debug('Calling %s_client.%s(*%r, **%r)',
                          self._service_type, '.'.join(self._path),
                          args, kwargs)
                method = self._get_attr(self._path, token, endpoint)
                return method(*args, **kwargs)
            except Exception as ex:
                LOG.debug('Error calling OpenStack client with args %r %r\n'
                          'Full stack trace:\n%s',
                          args, kwargs, ''.join(traceback.format_stack()),
                          exc_info=True)
                if hasattr(ex, 'http_status'):
                    http_status = getattr(ex, 'http_status')
                elif hasattr(ex, 'code'):
                    http_status = getattr(ex, 'code')
                else:
                    raise
                if do_retry and http_status in (401, 403):
                    discard_token(token)
                    token = get_token(self._credential, self._scope)
                else:
                    raise

    def _get_attr(self, path, token, endpoint):
        current = self._factory_fn(token, endpoint)
        for element in path:
            current = getattr(current, element)
        return current


def _get_authenticated_v2_client(credential, scope):
    try:
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
    except ks_exceptions.Unauthorized:
        LOG.error('Authentication with credentials %r in scope %r failed.',
                  credential, scope)
        raise


def get_token(credential, scope):
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
                    LOG.error('Failed to find %s endpoint from keystone, '
                              'check region name', service_type)
                    continue
            _tokens[token_key] = new_token
            _tokens[new_token] = token_key
            if token in _tokens:
                del _tokens[token]
            token = new_token
        return token


def get_endpoint(credential, scope, service_type):
    with _lock:
        try:
            result = _endpoints[credential, scope, service_type]
            LOG.debug('Retrieving endpoint for credential %r for scope %r for '
                      'service %s, result: %s',
                      credential, scope, service_type, result)
            return result
        except KeyError:
            LOG.error('Failed to retrieve endpoint for credential %r for'
                      'scope %r for service %s',
                      credential, scope, service_type)
            raise


def discard_token(token):
    with _lock:
        LOG.debug('Discarding token %s', token)
        try:
            key = _tokens.pop(token)
            if _tokens[key] == token:
                del _tokens[key]
        except KeyError:
            pass


def _prepare_credential_and_scope(cloud, scope):
    credential = cloud.credential
    if scope is None:
        scope = cloud.scope
    return credential, scope


def identity_client(cloud, scope=None):
    credential, scope = _prepare_credential_and_scope(cloud, scope)

    def factory_fn(token, endpoint):
        return v2_0_client.Client(token=token,
                                  endpoint=endpoint,
                                  endpoint_override=endpoint,
                                  insecure=credential.https_insecure,
                                  cacert=credential.https_cacert)
    return ClientProxy(factory_fn, cloud, credential, scope,
                       service_type=consts.ServiceType.IDENTITY)


def compute_client(cloud, scope=None):
    credential, scope = _prepare_credential_and_scope(cloud, scope)

    def factory_fn(token, endpoint):
        client = nova.Client(auth_token=token,
                             insecure=credential.https_insecure,
                             cacert=credential.https_cacert)
        client.set_management_url(endpoint)
        return client

    return ClientProxy(factory_fn, cloud, credential, scope,
                       service_type=consts.ServiceType.COMPUTE)


def network_client(cloud, scope=None):
    credential, scope = _prepare_credential_and_scope(cloud, scope)

    def factory_fn(token, endpoint):
        return neutron.Client(token=token,
                              endpoint_url=endpoint,
                              insecure=credential.https_insecure,
                              cacert=credential.https_cacert)

    return ClientProxy(factory_fn, cloud, credential, scope,
                       service_type=consts.ServiceType.NETWORK)


def image_client(cloud, scope=None):
    credential, scope = _prepare_credential_and_scope(cloud, scope)

    def factory_fn(token, endpoint):
        endpoint = re.sub(r'v(\d)/?$', '', endpoint)
        return glance.Client(endpoint=endpoint,
                             token=token,
                             insecure=credential.https_insecure,
                             cacert=credential.https_cacert)

    return ClientProxy(factory_fn, cloud, credential, scope,
                       service_type=consts.ServiceType.IMAGE)


def volume_client(cloud, scope=None):
    credential, scope = _prepare_credential_and_scope(cloud, scope)

    def factory_fn(token, endpoint):
        client = cinder.Client(insecure=credential.https_insecure,
                               cacert=credential.https_cacert)
        client.client.management_url = endpoint
        client.client.auth_token = token
        return client

    return ClientProxy(factory_fn, cloud, credential, scope,
                       service_type=consts.ServiceType.VOLUME)


def retry(func, *args, **kwargs):
    """
    Call function passed as first argument passing any remaining arguments
    and keyword arguments. If function fail with exception, it is called
    again after waiting for few seconds (specified by
    ``OpenstackCloud.request_attempts`` configuration parameter). It stops
    retrying after ``OpenstackCloud.request_failure_sleep`` unsuccessful
    attempts were made.
    :param func: function, bound method or some other callable
    :param expected_exceptions: tuple/list of exceptions that are expected
                                and handled, e.g. there is no need to retry
                                if such exception is caught
    :param returns_iterable: set it to True if func is expected to return
                             iterable
    :return: whatever func returns
    """
    # pylint: disable=protected-access

    expected_exceptions = kwargs.pop('expected_exceptions', None)
    returns_iterable = kwargs.pop('returns_iterable', False)
    assert isinstance(func, ClientProxy)
    cloud = func._cloud

    retry_obj = retrying.Retry(
        max_attempts=cloud.request_attempts,
        timeout=cloud.request_failure_sleep,
        expected_exceptions=expected_exceptions,
        reraise_original_exception=True)
    if returns_iterable:
        return retry_obj.run(lambda *a, **kw: [x for x in func(*a, **kw)],
                             *args, **kwargs)
    else:
        return retry_obj.run(func, *args, **kwargs)


class Timeout(Exception):
    """
    Exception is raised when some operation didn't complete in time.
    """


def wait_for(predicate, client, *args, **kwargs):
    """
    Periodically call predicate with client, *args, **kwargs arguments until it
    return True. If <cloud>.operation_timeout (from configuration) amount of
    seconds pass since beginning of wait, then Timeout exception is raised.
    """
    # pylint: disable=protected-access

    assert isinstance(client, ClientProxy)
    cloud = client._cloud

    operation_timeout = cloud.operation_timeout
    waited = 0.0
    sleep_time = 1.0
    while waited <= operation_timeout:
        time.sleep(
            max(1.0, min(sleep_time, operation_timeout - waited)))
        waited += sleep_time
        sleep_time *= 1.5
        result = predicate(client, *args, **kwargs)
        if result:
            return result
    raise Timeout()
