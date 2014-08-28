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


from novaclient.v1_1 import client as novaClient
from cinderclient.v1 import client as cinderClient
from glanceclient.v1 import client as glanceClient
from keystoneclient.v2_0 import client as keystoneClient

NOVA_SERVICE = "nova"


class osCommon(object):

    """

    Common class for getting openstack client objects

    """

    def __init__(self, config):
        self.keystone_client = self.get_keystone_client(config)
        self.nova_client = self.get_nova_client(config)
        self.cinder_client = self.get_cinder_client(config)
        self.network_client = self.get_network_client(config, self.detect_network_client(self.keystone_client))
        self.glance_client = self.get_glance_client(self.keystone_client)
        self.keystone_db_conn_url = self.compose_keystone_db_conn_url(config)

    @staticmethod
    def get_nova_client(params):

        """ Getting nova client """

        return novaClient.Client(params["user"],
                                 params["password"],
                                 params["tenant"],
                                 "http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_cinder_client(params):

        """ Getting cinder client """

        return cinderClient.Client(params["user"],
                                   params["password"],
                                   params["tenant"],
                                   "http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def detect_network_client(keystone):
        if osCommon.get_name_service_by_type(keystone, 'network') == "quantum":
            from quantumclient.v2_0 import client as networkClient
        if osCommon.get_name_service_by_type(keystone, 'network') == "neutron":
            from neutronclient.v2_0 import client as networkClient
        else:
            return None
        return networkClient


    @staticmethod
    def get_network_client(params, network_client):
        """ Getting neutron(quantun) or nova client """
        if network_client:
            return network_client.Client(username=params["user"],
                                         password=params["password"],
                                         tenant_name=params["tenant"],
                                         auth_url="http://" + params["host"] + ":35357/v2.0/")
        else:
            return novaClient.Client(params["user"],
                                     params["password"],
                                     params["tenant"],
                                     "http://" + params["host"] + ":35357/v2.0/")

    def network_service(self):
        return 'nova' if type(self.nova_client) == type(self.network_client) \
            else 'neutron'

    @staticmethod
    def get_keystone_client(params):

        """ Getting keystone client """

        keystoneClientForToken = keystoneClient.Client(username=params["user"],
                                                       password=params["password"],
                                                       tenant_name=params["tenant"],
                                                       auth_url="http://" + params["host"] + ":35357/v2.0/")
        return keystoneClient.Client(token=keystoneClientForToken.auth_ref["token"]["id"],
                                     endpoint="http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_glance_client(keystone_client):

        """ Getting glance client """

        endpoint_glance = osCommon.get_endpoint_by_name_service(keystone_client, 'glance')
        return glanceClient.Client(endpoint_glance, token=keystone_client.auth_token_from_user)

    @staticmethod
    def get_id_service(keystone_client, name_service):

        """ Getting service_id from keystone """

        for service in keystone_client.services.list():
            if service.name == name_service:
                return service
        return None

    @staticmethod
    def get_name_service_by_type(keystone_client, type_service):

        """ Getting service_name from keystone """

        for service in keystone_client.services.list():
            if service.type == type_service:
                return service.name
        return NOVA_SERVICE

    @staticmethod
    def get_public_endpoint_service_by_id(keystone_client, service_id):
        for endpoint in keystone_client.endpoints.list():
            if endpoint.service_id == service_id:
                return endpoint.publicurl
        return None

    @staticmethod
    def get_endpoint_by_name_service(keystone_client, name_service):
        return osCommon.get_public_endpoint_service_by_id(keystone_client, osCommon.get_id_service(keystone_client,
                                                                                                   name_service).id)

    @staticmethod
    def compose_keystone_db_conn_url(params):

        """ Compose keystone database connection url for SQLAlchemy """

        return '{}://{}:{}@{}/keystone'.format(params['identity']['connection'], params['user'], params['password'],
                                               params['host'])

    @staticmethod
    def get_tenant_id_by_name(keystone_client, name):
        for i in keystone_client.tenants.list():
            if i.name == name:
                return i.id