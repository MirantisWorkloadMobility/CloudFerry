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
        return keystoneClient.Client(username=params["user"],
                                     password=params["password"],
                                     tenant_name=params["tenant"],
                                     auth_url="http://" + params["host"] + ":35357/v2.0/")

    @staticmethod
    def get_glance_client(params, keystone_client):
        return glanceClient.Client(params["endpoint_glance"], token=keystone_client.auth_ref["token"]["id"])

    @staticmethod
    def wait_for_status(getter, id, status):
        while getter.get(id).status != status:
            time.sleep(1)