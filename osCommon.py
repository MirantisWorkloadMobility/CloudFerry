from novaclient.v1_1 import client as novaClient
from cinderclient.v1 import client as cinderClient
#from quantumclient.v2_0 import client as quantumClient
from neutronclient.v2_0 import client as quantumClient
from glanceclient.v2 import client as glanceClient
from keystoneclient.v2_0 import client as keystoneClient
import time


class osCommon(object):
    
    def __init__(self, config):
        self.keystone_client = self.get_keystone_client(config)
        config["endpoint_glance"] = self.get_endpoint_by_name_service(self.keystone_client, 'glance')
        self.nova_client = self.get_nova_client(config)
        self.cinder_client = self.get_cinder_client(config)
        self.quantum_client = self.get_quantum_client(config)
        self.glance_client = self.get_glance_client(config, self.keystone_client)
        self.config = config
        
    @staticmethod
    def get_nova_client(params):
        return novaClient.Client(params["user"],
                                 params["password"],
                                 params["tenant"],
                                 "http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_cinder_client(params):
        return cinderClient.Client(params["user"],
                                   params["password"],
                                   params["tenant"],
                                   "http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_quantum_client(params):
        return quantumClient.Client(username=params["user"],
                                    password=params["password"],
                                    tenant_name=params["tenant"],
                                    auth_url="http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_keystone_client(params):
        keystoneClientForToken = keystoneClient.Client(username=params["user"],
                                                       password=params["password"],
                                                       tenant_name=params["tenant"],
                                                       auth_url="http://" + params["host"] + ":35357/v2.0/")
        return keystoneClient.Client(token=keystoneClientForToken.auth_ref["token"]["id"],
                                     endpoint="http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_glance_client(params, keystone_client):
        return glanceClient.Client(params["endpoint_glance"], token=keystone_client.auth_token_from_user)

    @staticmethod
    def get_id_service(keystone_client, name_service):
        for service in keystone_client.services.list():
            if service.name == name_service:
                return service
        return None

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
    def wait_for_status(getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)